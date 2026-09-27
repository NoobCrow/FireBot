import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

GPIO.setup(19, GPIO.OUT)

tiltservo = GPIO.PWM(19, 50)  # GPIO 19 for PWM with 50Hz
tiltservo.start(0)

time.sleep(2)

tiltservo.ChangeDutyCycle(10)
time.sleep(1)







tiltservo.stop()
GPIO.cleanup()

print("Goodbye")
