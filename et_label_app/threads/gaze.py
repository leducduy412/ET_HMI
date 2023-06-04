import time

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

from pylsl import StreamInlet, resolve_byprop


class GazeThread(QtCore.QThread):
    point_signal = QtCore.Signal(object)

    def run(self):
        # window size
        win_size = QtWidgets.QDesktopWidget().screenGeometry(-1)
        win_size_height = win_size.height()
        win_size_width = win_size.width()

        # gaze stream
        try:
            streams = resolve_byprop("name", "TobiiStreamEngine_gaze", 1, 2)
            inlet = StreamInlet(streams[0])
            point_type = "gaze"
        except:
            print("Timed out for operation TobiiStreamEngine_gaze, use mouse instead")
            point_type = "mouse"

        while True:
            if point_type == "gaze":
                chunk, timestamps = inlet.pull_chunk()
                if timestamps:
                    try:
                        self.point_signal.emit((
                            timestamps[-1],
                            QtCore.QPoint(
                                int(chunk[-1][0]*win_size_width),
                                int(chunk[-1][1]*win_size_height)
                            )
                        ))
                    except:
                        pass # some point is None
            elif point_type == "mouse":
                self.point_signal.emit((
                    time.time(),
                    QtGui.QCursor().pos()
                ))
                time.sleep(0.001)
