import time, random, subprocess, os
import datetime as dt
import picamera

def take():
    print('take video start')
    
    camera = picamera.PiCamera()

    name = str(time.time()) + '_' + str(random.randint(0,1000000))
    videoH264Path = 'static/videos/' + name + '.h264'
    videoPath = 'static/videos/' + name + '.mp4'
    imagePath = 'static/videos/' + name + '.jpg'
    duration = 5
    
    # camera settings
    camera.resolution = (480, 480)
    camera.zoom = (0.1, 0.0, 0.8, 0.8)
    camera.framerate = 30

    # capture image to video preview
    camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    camera.capture(imagePath)
    
    # record video and capture image
    camera.start_recording(videoH264Path)
    start = dt.datetime.now()
    while (dt.datetime.now() - start).seconds < duration:
        camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        camera.wait_recording(0.2)
    camera.stop_recording()
    
    camera.close()

    # h264 to mp4
    subprocess.run(['MP4Box', '-fps', '30', '-add', videoH264Path, videoPath])
    os.remove(videoH264Path)

    print('video ' + videoPath + ' image ' + imagePath)

    return (videoPath, imagePath)

if __name__ == '__main__':
    data = take()

