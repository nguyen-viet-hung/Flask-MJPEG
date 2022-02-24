from flask import Flask, Response
from threading import Thread, Lock
from time import perf_counter, sleep
from PIL import ImageFont, ImageDraw, Image
import cv2
import io
from datetime import datetime

app = Flask(__name__)

# this is based on https://github.com/janakj/py-mjpeg
def mjpeg_generator(boundary, frames):
    hdr = '--%s\r\nContent-Type: image/jpeg\r\n' % boundary

    prefix = ''
    for f in frames:
        msg = prefix + hdr + 'Content-Length: %d\r\n\r\n' % len(f)
        yield msg.encode('utf-8') + f
        prefix = '\r\n'


def MJPEGResponse(it):
    boundary='herebedragons'
    return Response(mjpeg_generator(boundary, it), mimetype='multipart/x-mixed-replace;boundary=%s' % boundary)


def get_datetime_str():
    now = datetime.now()
    d1 = now.strftime("%Y-%m-%d %H:%M:%S")
    return d1


# ============ class VideoStream ===========
class VideoStream :
    def __init__(self, cap_url:str, cap_loop: bool) :
        self.stream = cv2.VideoCapture(cap_url)
        (self.grabbed, self.frame) = self.stream.read()
        self.started = False
        self.cap_loop = cap_loop
        self.cap_url = cap_url
        self.read_lock = Lock()

    def start(self) :
        if self.started :
            print("already started!!")
            return None
        self.started = True
        self.thread = Thread(target=self.update, args=())
        self.thread.start()
        return self

    def update(self) :
        while self.started :
            (grabbed, frame) = self.stream.read()
            if not grabbed:
                print(get_datetime_str(), " WARNING: no frame grabbed!")
                if self.cap_loop:
                    self.stream.release()
                    self.stream.open(self.cap_url)
                    print(get_datetime_str(), " INFO: trying to re-open the video capture")
                    continue
                else:
                    self.stream.release()
                    print(get_datetime_str(), " WARNING: no loop request. Will terminate the capture thread")
                    break

            self.read_lock.acquire()
            self.grabbed, self.frame = grabbed, frame
            self.read_lock.release()
            sleep(0.04)

    def read(self) :
        self.read_lock.acquire()
        if not isinstance(self.frame, type(None)):
            frame = self.frame.copy()
        else:
            frame = None
        self.read_lock.release()
        return frame

    def stop(self) :
        self.started = False
        if self.thread.is_alive():
            self.thread.join()

    def get_fps(self) -> int:
        return int(self.stream.get(cv2.CAP_PROP_FPS))

    def get_width(self) -> int:
        return int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    def get_height(self) -> int:
        return int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def __exit__(self, exc_type, exc_value, traceback) :
        self.stream.release()

# create a video capture
new_thread = VideoStream(cap_url=0, cap_loop=True)
new_thread.start()

def relay():
    while True:
        # grab frame
        img = new_thread.read()
        cv2_im_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(cv2_im_rgb)

        # save frame to JPEG into memory
        buf= io.BytesIO()
        pil_im.save(buf, format= 'JPEG')
        frame = buf.getvalue()

        # return the buffer to handler
        yield frame
        sleep(0.04)
        

@app.route('/')
def stream():
    return MJPEGResponse(relay())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
    new_thread.stop()