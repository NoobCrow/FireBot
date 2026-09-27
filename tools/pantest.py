import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

GPIO.setup(18, GPIO.OUT)

panservo = GPIO.PWM(18, 50)  
panservo.start(0)

time.sleep(2)

panservo.ChangeDutyCycle(3)
time.sleep(1)
panservo.ChangeDutyCycle(10)
time.sleep(1)

panservo.stop()
GPIO.cleanup()

print("Goodbye")
