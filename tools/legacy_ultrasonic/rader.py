from gpiozero import Servo
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()

tilt = Servo(
    12,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)

print("Tilt middle")
tilt.value = 0.3
sleep(3)

print("Tilt minimum")
tilt.value = -1
sleep(3)

print("Tilt middle")
tilt.value = 0.0
sleep(3)

print("Tilt maximum")
tilt.value = 1
sleep(3)

print("Tilt middle")
tilt.value = 0.0
sleep(3)

tilt.value = None
