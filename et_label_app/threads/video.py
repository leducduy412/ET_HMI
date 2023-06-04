import time
import cv2

from qtpy import QtCore
from qtpy import QtGui

from et_label_app.utils import img_npy_to_qimage


class VideoThread(QtCore.QThread):
    video_signal = QtCore.Signal(QtGui.QPixmap)
    video_path = None
    video_info = None
    play = False

    def run(self):
        # init value
        video_path = None
        fps = None
        height = None
        width = None
        cap = None

        # run
        while True:
            # create cap
            if self.video_path != video_path:
                video_path = self.video_path
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = cv2.CAP_PROP_FRAME_WIDTH
                height = cv2.CAP_PROP_FRAME_HEIGHT
                self.video_info = {
                    "video_path": video_path,
                    "fps": fps,
                    "width": width,
                    "height": height
                }
                self.read_next = True
                self.frame_idx = -1

            if cap is not None and cap.isOpened() and self.play:
                ret, frame = cap.read()
                if ret == True:
                    self.frame_idx += 1
                    self.video_signal.emit(
                        QtGui.QPixmap.fromImage(
                            img_npy_to_qimage(frame)
                        )
                    )
            else:
                self.stop_video()

            if cap is None or not self.play:
                time.sleep(0.01)
            else:
                time.sleep(1/fps)

    def load_video(self, video_path):
        self.video_path = video_path

    def start_video(self):
        self.play = True

    def stop_video(self):
        self.play = False
