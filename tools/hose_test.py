from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep

HOSE_PIN = 10   # Physical pin 19

factory = PiGPIOFactory()

servo = Servo(
    HOSE_PIN,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)

print("Hose servo MAX <-> MIN test")
print("Press Ctrl+C to stop")

try:
    while True:

        # MAX → MIN
        print("MAX → MIN")
        servo.value = 1.0
        sleep(1)

        servo.value = 0.5
        sleep(0.5)

        servo.value = 0.0
        sleep(0.5)

        servo.value = -0.5
        sleep(0.5)

        servo.value = -1.0
        sleep(1)

        # MIN → MAX
        print("MIN → MAX")
        servo.value = -0.5
        sleep(0.5)

        servo.value = 0.0
        sleep(0.5)

        servo.value = 0.5
        sleep(0.5)

        servo.value = 1.0
        sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    servo.value = 0
    sleep(0.5)
    servo.detach()
