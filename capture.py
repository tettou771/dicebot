import picamera

camera = picamera.PiCamera()

videoName = 'tmp/diceVideo.mp4'
pictureName = 'tmp/dicePicture.jpg'
duration = 5

# record video and capture image
camera.start_recording(videoName)
sleep(duration)
camera.stop_recording()
camera.capture(pictureName)

# send to nextcloud

