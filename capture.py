import time, random, subprocess, os
import datetime as dt
import picamera

def take():
    print('take video start')
    
    camera = picamera.PiCamera()

    name = str(time.time()) + '_' + str(random.randint(0,1000000))
    videoH264Path = 'static/videos/' + name + '.h264'
    videoPath = 'static/videos/' + name + '.mp4'
    thumPath = 'static/videos/' + name + '_thumb.jpg'
    resultPath = 'static/videos/' + name + '_result.jpg'
    duration = 5
    
    # camera settings
    camera.resolution = (480, 480)
    camera.zoom = (0.1, 0.0, 0.8, 0.8)
    camera.framerate = 30

    # capture image to video thumbnail (not result)
    camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    camera.capture(thumPath)
    
    # record video and capture image
    camera.start_recording(videoH264Path)
    start = dt.datetime.now()
    while (dt.datetime.now() - start).seconds < duration:
        camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        camera.wait_recording(0.2)
    camera.stop_recording()

    # capture image to result (after roll the dice)
    camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    camera.capture(resultPath)

    camera.close()

    # h264 to mp4
    subprocess.run(['MP4Box', '-fps', '30', '-add', videoH264Path, videoPath])
    os.remove(videoH264Path)

    print('video ' + videoPath + ' thumb ' + thumPath + ' result ' + resultPath)

    return (videoPath, thumPath, resultPath)

if __name__ == '__main__':
    data = take()

