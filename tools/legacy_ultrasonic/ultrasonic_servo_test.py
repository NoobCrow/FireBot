from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep

SERVO_PIN = 26

factory = PiGPIOFactory()
servo = Servo(
    SERVO_PIN,
    pin_factory=factory,
    min_pulse_width=0.001,
    max_pulse_width=0.002
)

print("Ultrasonic Servo Test")
print("=====================")

try:
    print("Center")
    servo.value = 0
    sleep(2)

    print("min")
    servo.value = -1
    sleep(2)

    print("Center")
    servo.value = 0
    sleep(2)

    print("max")
    servo.value = 1
    sleep(2)

    print("Center")
    servo.value = 0
    sleep(2)

finally:
    servo.detach()
    print("Servo released")
