from picamera2 import Picamera2
picam2 = Picamera2()
picam2.start(show_preview=False)
print(picam2.camera_controls)
picam2.stop()
