import functools
import math
import io
import os.path as osp

from qtpy import QtCore
from qtpy.QtCore import Qt
from qtpy import QtGui
from qtpy import QtWidgets

import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = None

from et_label_app import __appname__

from . import utils
from et_label_app.config import get_config
from et_label_app.widgets import FileDialogPreview
from et_label_app.widgets import ToolBar
from et_label_app.widgets import ZoomWidget
from et_label_app.widgets import Canvas


def load_image_file(filename):
    try:
        image_pil = PIL.Image.open(filename)
    except IOError:
        print("Failed opening image file: {}".format(filename))
        return

    with io.BytesIO() as f:
        ext = osp.splitext(filename)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            format = "JPEG"
        else:
            format = "PNG"
        image_pil.save(f, format=format)
        f.seek(0)
        return f.read()


class MainWindow(QtWidgets.QMainWindow):

    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2

    def __init__(self, config=None):
        if config is None:
            config = get_config()
        self._config = config

        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        self.statusBar().showMessage(str(self.tr("%s started.")) % __appname__)
        self.statusBar().show()

        # create canvas
        self.canvas = Canvas()

        # set zoom
        self.zoomWidget = ZoomWidget()
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.zoomWidget.valueChanged.connect(self.paintCanvas)
        self.zoomMode = self.FIT_WINDOW
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            self.MANUAL_ZOOM: lambda: 1
        }

        # set scroll
        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(self.canvas)
        scrollArea.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scrollArea.verticalScrollBar(),
            Qt.Horizontal: scrollArea.horizontalScrollBar()
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        # set central widget
        self.setCentralWidget(scrollArea)

        # actions
        action = functools.partial(utils.newAction, self)
        shortcuts = self._config["shortcuts"]
        self.open_action = action(
            self.tr("&Open"),
            self.openFile,
            shortcuts["open"],
            "open",
            self.tr("Open image or label file")
        )
        self.start_rec_action = action(
            self.tr("&Start"),
            self.start_rec,
            None,
            "start-video",
            self.tr("Start recording"),
            enabled=False
        )

        # state
        self.image = QtGui.QImage()
        self.zoom_values = {}
        self.scroll_values = {
            Qt.Horizontal: {},
            Qt.Vertical: {}
        }
        self.filename = None

        # setting
        self.settings = QtCore.QSettings("VNU", "et_label_app")
        self.recentFiles = self.settings.value("recentFiles", []) or []
        size = self.settings.value("window/size", QtCore.QSize(600, 500))
        position = self.settings.value("window/position", QtCore.QPoint(0, 0))
        state = self.settings.value("window/state", QtCore.QByteArray())
        self.resize(size)
        self.move(position)
        self.restoreState(state)

        # tool bar
        self.tools = self.toolbar("Tools")
        utils.addActions(self.tools, (
            self.open_action,
            None,
            self.start_rec_action,
            None
        ))

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            utils.addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar

    def setClean(self):
        self.start_rec_action.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}".format(title, self.filename)
        self.setWindowTitle(title)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.filename = None
        self.canvas.resetState()

    def scrollRequest(self, delta, orientation):
        units = -delta * 0.1
        bar = self.scrollBars[orientation]
        value = bar.value() + bar.singleStep() * units
        self.setScroll(orientation, value)

    def setScroll(self, orientation, value):
        self.scrollBars[orientation].setValue(int(value))
        self.scroll_values[orientation][self.filename] = value

    def setZoom(self, value):
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def addZoom(self, increment=1.1):
        zoom_value = self.zoomWidget.value() * increment
        if increment > 1:
            zoom_value = math.ceil(zoom_value)
        else:
            zoom_value = math.floor(zoom_value)
        self.setZoom(zoom_value)

    def zoomRequest(self, delta, pos):
        canvas_width_old = self.canvas.width()
        units = 1.1
        if delta < 0:
            units = 0.9
        self.addZoom(units)
        canvas_width_new = self.canvas.width()
        if canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old
            x_shift = round(pos.x() * canvas_scale_factor) - pos.x()
            y_shift = round(pos.y() * canvas_scale_factor) - pos.y()
            self.setScroll(
                Qt.Horizontal,
                self.scrollBars[Qt.Horizontal].value() + x_shift,
            )
            self.setScroll(
                Qt.Vertical,
                self.scrollBars[Qt.Vertical].value() + y_shift,
            )

    def setFitWindow(self, value=True):
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def loadFile(self, filename=None):
        self.resetState()
        self.canvas.setEnabled(False)
        if filename is None:
            filename = self.settings.value("filename", "")
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr("No such file: <b>%s</b>") % filename,
            )
            return False
        self.status(
            str(self.tr("Loading %s...")) % osp.basename(str(filename))
        )
        self.filename = filename  # use this value as key value

        # load image / video data
        ext = osp.splitext(filename)[1].lower()
        if ext in [".mp4"]:
            image = utils.get_video_first_frame(filename)
            self.canvas.load_video(filename)
        else:
            image = QtGui.QImage.fromData(
                load_image_file(filename)
            )

        # check read ok
        if image.isNull():
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr(
                    "<p>Make sure <i>{0}</i> is a valid image file.<br/>"
                    "Supported image formats: {1}</p>"
                ).format(filename, ",".join(self.formats)),
            )
            self.status(self.tr("Error reading %s") % filename)
            return False

        # load pixmap
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(image))
        self.canvas.setEnabled(True)
        self.setClean()
        self.image = image

        # set zoom values
        if self.filename in self.zoom_values:
            self.zoomMode = self.zoom_values[self.filename][0]
            self.setZoom(self.zoom_values[self.filename][1])
        else:
            self.adjustScale(initial=True)

        # set scroll values
        for orientation in self.scroll_values:
            if self.filename in self.scroll_values[orientation]:
                self.setScroll(
                    orientation, self.scroll_values[orientation][self.filename]
                )

        # canvas
        self.paintCanvas()
        self.canvas.setFocus()

        # status
        self.status(str(self.tr("Loaded %s")) % osp.basename(str(filename)))

        return True

    def resizeEvent(self, event):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        value = int(100 * value)
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def scaleFitWindow(self):
        e = 2.0
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("recentFiles", self.recentFiles)

    def openFile(self, _value=False):
        path = osp.dirname(str(self.filename)) if self.filename else "."
        self.formats = [
            "*.{}".format(fmt.data().decode())
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ] + ["*.mp4"]
        filters = self.tr("Image & Video (%s)") % " ".join(self.formats)
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose Image or Label file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        if fileDialog.exec_():
            fileName = fileDialog.selectedFiles()[0]
            if fileName:
                self.loadFile(fileName)

    def start_rec(self, _value=False):
        self.canvas.start_rec()

    def errorMessage(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )
