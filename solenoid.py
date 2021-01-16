import RPi.GPIO as gpio
import time, threading

solenoidPin = 18
thread = threading

def push(durationSec):
    gpio.output(solenoidPin, 1)
    time.sleep(durationSec)
    gpio.output(solenoidPin, 0)

def renda():
    gpio.setmode(gpio.BCM)
    gpio.setup(solenoidPin, gpio.OUT)
    pushSec = 0.01
    waitSec = 0.3
    pushTimes = 10
    for i in range(0, pushTimes):
        push(pushSec)
        time.sleep(waitSec)
    gpio.cleanup(solenoidPin)
	
def renda_threaded():
    thread = threading.Thread(target = renda)
    thread.start()

if __name__ == '__main__':
    renda_threaded()
    print('renda')
