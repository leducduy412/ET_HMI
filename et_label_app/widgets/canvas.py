import copy

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

from et_label_app import QT5
import et_label_app.utils
from et_label_app.threads.gaze import GazeThread
from et_label_app.threads.video import VideoThread


class Shape(object):
    line_color = QtGui.QColor(0, 255, 0, 128)
    vertex_fill_color = QtGui.QColor(0, 255, 0, 255)
    point_type = "round"  # round / square
    point_size = 8
    scale = 1.0

    def __init__(self):
        self.points = []

    def addPoint(self, point):
        self.points.append(point)
        if len(self.points) == 10:
            self.points = self.points[1:]

    def paint(self, painter):
        if self.points:
            pen = QtGui.QPen(self.line_color)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QtGui.QPainterPath()
            vrtx_path = QtGui.QPainterPath()

            line_path.moveTo(self.points[0])
            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                self.drawVertex(vrtx_path, i)

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self._vertex_fill_color)

    def drawVertex(self, path, i):
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        self._vertex_fill_color = self.vertex_fill_color
        if shape == "square":
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == "round":
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"

    def copy(self):
        return copy.deepcopy(self)

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value


class Canvas(QtWidgets.QWidget):

    zoomRequest = QtCore.Signal(int, QtCore.QPoint)
    scrollRequest = QtCore.Signal(int, int)

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        self.current = None  # current shape
        self.line = Shape()  # moving line
        self.scale = 1.0
        self.pixmap = QtGui.QPixmap()
        self._painter = QtGui.QPainter()

        self.is_paint = True
        self.is_rec = False

        self.gaze_thread_timestamp_temp = None
        self.gaze_thread = GazeThread()
        self.gaze_thread.point_signal.connect(self.read_gaze_signal)
        self.gaze_thread.start()

        self.content_type = "image"  # image / video
        self.video_thresh = VideoThread()
        self.video_thresh.video_signal.connect(self.read_video_frame)
        self.video_thresh.start()

    def start_rec(self):
        if self.content_type == "video":
            self.video_thresh.start_video()
        self.is_rec = True

    def load_video(self, video_path):
        self.content_type = "video"
        self.video_thresh.load_video(video_path)

    def read_video_frame(self, video_signal):
        self.loadPixmap(video_signal)

    def read_gaze_signal(self, point_signal):
        if not self.is_rec:
            return

        timestamp, point = point_signal
        pos = self.transformPos(self.mapFromGlobal(point))

        ### save gaze here ###

        if self.is_paint:
            if self.gaze_thread_timestamp_temp is None:
                self.gaze_thread_timestamp_temp = [timestamp, timestamp]
            if timestamp - self.gaze_thread_timestamp_temp[0] > 0.05:
                self.move_point(pos)
                self.gaze_thread_timestamp_temp[0] = timestamp
            if timestamp - self.gaze_thread_timestamp_temp[1] > 1:
                self.save_point(pos)
                self.gaze_thread_timestamp_temp[1] = timestamp

    def move_point(self, pos):
        if not self.current:
            self.repaint()
            return

        if self.outOfPixmap(pos):
            pos = self.intersectionPoint(self.current[-1], pos)

        self.line[0] = self.current[-1]
        self.line[1] = pos
        self.repaint()

    def save_point(self, pos):
        if self.current:
            # Add point to existing shape.
            self.current.addPoint(self.line[1])
            self.line[0] = self.current[-1]
        elif not self.outOfPixmap(pos):
            # Create new shape.
            self.current = Shape()
            self.current.addPoint(pos)
            self.line.points = [pos, pos]
            self.update()

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())

        p.drawPixmap(0, 0, self.pixmap)

        Shape.scale = self.scale
        if self.current:
            self.current.paint(p)
            self.line.paint(p)

        if (
            self.current is not None
            and len(self.current.points) >= 2
        ):
            drawing_shape = self.current.copy()
            drawing_shape.addPoint(self.line[1])
            drawing_shape.paint(p)

        p.end()

    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical ones."""
        return point / self.scale - self.offsetToCenter()

    def offsetToCenter(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QtCore.QPointF(x, y)

    def outOfPixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w - 1 and 0 <= p.y() <= h - 1)

    def intersectionPoint(self, p1, p2):
        # Cycle through each image edge in clockwise fashion,
        # and find the one intersecting the current line segment.
        # http://paulbourke.net/geometry/lineline2d/
        size = self.pixmap.size()
        points = [
            (0, 0),
            (size.width() - 1, 0),
            (size.width() - 1, size.height() - 1),
            (0, size.height() - 1),
        ]
        # x1, y1 should be in the pixmap, x2, y2 should be out of the pixmap
        x1 = min(max(p1.x(), 0), size.width() - 1)
        y1 = min(max(p1.y(), 0), size.height() - 1)
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QtCore.QPointF(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QtCore.QPointF(min(max(0, x2), max(x3, x4)), y3)
        return QtCore.QPointF(x, y)

    def intersectingEdges(self, point1, point2, points):
        """Find intersecting edges.

        For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen.
        """
        (x1, y1) = point1
        (x2, y2) = point2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QtCore.QPointF((x3 + x4) / 2, (y3 + y4) / 2)
                d = et_label_app.utils.distance(m - QtCore.QPointF(x2, y2))
                yield d, i, (x, y)

    # These two, along with a call to adjustSize are required for the scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        if QT5:
            mods = ev.modifiers()
            delta = ev.angleDelta()
            if QtCore.Qt.ControlModifier == int(mods):
                # zoom (with Ctrl/Command key)
                self.zoomRequest.emit(delta.y(), ev.pos())
            else:
                # scroll
                self.scrollRequest.emit(delta.x(), QtCore.Qt.Horizontal)
                self.scrollRequest.emit(delta.y(), QtCore.Qt.Vertical)
        else:
            if ev.orientation() == QtCore.Qt.Vertical:
                mods = ev.modifiers()
                if QtCore.Qt.ControlModifier == int(mods):
                    self.zoomRequest.emit(ev.delta(), ev.pos())
                else:
                    self.scrollRequest.emit(
                        ev.delta(),
                        QtCore.Qt.Horizontal
                        if (QtCore.Qt.ShiftModifier == int(mods))
                        else QtCore.Qt.Vertical,
                    )
            else:
                self.scrollRequest.emit(ev.delta(), QtCore.Qt.Horizontal)
        ev.accept()

    def loadPixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def resetState(self):
        self.pixmap = None
        self.update()
