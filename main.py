import keyboard
import sys

from collections import deque
from PIL import ImageGrab, ImageQt, Image
from PIL.Image import Resampling
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, QPoint, QTimer
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget
from screeninfo import get_monitors


TESTING = True
RESIZE_FACTOR = 2
OPACITY = 255
VANISH_DURATION = 2000


class ImageViewer(QWidget):
    pixmap = None
    _sizeHint = QSize()
    ratio = Qt.AspectRatioMode.KeepAspectRatio
    transformation = Qt.TransformationMode.SmoothTransformation

    def __init__(self, parent=None, pixmap=None):
        QWidget.__init__(self, parent=parent)
        self.scaled = None
        self.setPixmap(pixmap)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setPixmap(self, pixmap):
        if self.pixmap != pixmap:
            self.pixmap = pixmap
            if isinstance(pixmap, QPixmap):
                self._sizeHint = pixmap.size()
            else:
                self._sizeHint = QSize()
            self.updateGeometry()
            self.updateScaled()

    def setAspectRatio(self, ratio):
        if self.ratio != ratio:
            self.ratio = ratio
            self.updateScaled()

    def setTransformation(self, transformation):
        if self.transformation != transformation:
            self.transformation = transformation
            self.updateScaled()

    def updateScaled(self):
        if self.pixmap:
            self.scaled = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, self.transformation)
            # self.scaled = self.pixmap.scaled(self.size(), self.ratio, self.transformation)
        self.update()

    def sizeHint(self):
        return self._sizeHint

    def resizeEvent(self, event):
        self.updateScaled()

    def paintEvent(self, event):
        if not self.pixmap:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self.scaled.rect()
        r.moveCenter(self.rect().center())
        painter.drawPixmap(r, self.scaled)

    def flash(self):
        self.hide()
        restore_timer = QTimer(self)
        restore_timer.timeout.connect(self.show)
        restore_timer.setSingleShot(True)
        restore_timer.start(VANISH_DURATION)


def crop_image():
    img = ImageGrab.grabclipboard() if not TESTING else Image.open('jigsaw.png')
    img = img.convert('RGBA')
    copy = img.copy()
    copy_pixels = copy.load()
    for x in range(img.width):
        for y in range(img.height):
            (r, g, b, a) = copy_pixels[x, y]
            if abs(max(r, g, b) - min(r, g, b)) < 3:
                copy_pixels[x, y] = (0, 0, 0, 0)
            else:
                copy_pixels[x, y] = (r, g, b, OPACITY)
    cropped = img.crop(copy.getbbox())
    return cropped


def get_label(window, cropped, screen_size):
    pixmap = ImageQt.toqpixmap(cropped)
    label = ImageViewer()
    label.setPixmap(pixmap)
    label.setGeometry(0, 0, pixmap.width(), pixmap.height())
    width, height = screen_size
    window.resize(width // 2, height // 2)
    return label


class PaleWindow(QtWidgets.QWidget):
    def __init__(self, cropped, screen_size):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.Widget)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.opacityCycle = deque([.5, .75, .85, 1, .15, .25])
        self.setWindowOpacity(self.opacityCycle[0])

        layout = QtWidgets.QVBoxLayout()
        sizegrip = QtWidgets.QSizeGrip(self)
        self.image_label = get_label(self, cropped, screen_size)
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignHCenter |
                         Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(sizegrip, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignRight)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.oldPos = None
        self.flashEnabled = False
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        sizegrip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        keyboard.on_press_key('esc', lambda _: self.toggle_click(), suppress=True)

    def toggle_click(self):
        # attributes = [Qt.WidgetAttribute.WA_NoChildEventsForParent]
        # for attribute in attributes:
        #     self.setAttribute(attribute, not self.testAttribute(attribute))
        self.clearFocus()
        self.setWindowFlags(self.windowFlags() ^ (Qt.WindowType.BypassWindowManagerHint
                                                  | Qt.WindowType.WindowTransparentForInput))
        self.hide()
        self.show()

    def center(self):
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.opacityCycle.rotate(-1)
            self.setWindowOpacity(self.opacityCycle[0])
        # elif key == Qt.Key.Key_Escape:
        #     self.toggle_click()
        #

    def mousePressEvent(self, event):
        self.oldPos = event.position().toPoint()
        if event.button() == Qt.MouseButton.RightButton:
            self.flashEnabled = not self.flashEnabled
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.flashEnabled:
                self.image_label.flash()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.position().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())

    def mouseReleaseEvent(self, event):
        self.oldPos = event.position().toPoint()
        self.image_label.show()


def main():
    screen_size = None
    for monitor in get_monitors():
        if monitor.x == 0:
            screen_size = monitor.width, monitor.height
    cropped = crop_image()
    cropped = cropped.resize((cropped.width * RESIZE_FACTOR, cropped.height * RESIZE_FACTOR),
                             resample=Resampling.LANCZOS)
    app = QtWidgets.QApplication(sys.argv)
    window = PaleWindow(cropped, screen_size)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
