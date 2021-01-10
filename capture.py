import time, random
import picamera

def take:
    camera = picamera.PiCamera()

    name = str(time.time()) + '_' + str(random.randint(0,1000000))
    videoPath = 'static/videos/' + name + '.mp4'
    imagePath = 'static/videos/' + name + '.jpg'
    duration = 5

    # record video and capture image
    camera.start_recording(videoPath)
    sleep(duration)
    camera.stop_recording()
    camera.capture(imagePath)

    return (videoPath, imagePath)
if (name == '__main__'):
    data = take()
    print('video ' + data[0] + ' image ' + data[1])

