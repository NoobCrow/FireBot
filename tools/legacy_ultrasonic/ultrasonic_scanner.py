import RPi.GPIO as GPIO
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep, time


# ============================================================
# FIREBOT ULTRASONIC SCANNER
# ============================================================

TRIG = 16          # Physical pin 36
ECHO = 20          # Physical pin 38
SERVO_PIN = 26     # Physical pin 37


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(TRIG, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ECHO, GPIO.IN)


factory = PiGPIOFactory()

scanner = Servo(
    SERVO_PIN,
    min_pulse_width=0.0005,
    max_pulse_width=0.0025,
    pin_factory=factory
)


# ============================================================
# DISTANCE FUNCTION
# ============================================================

def get_distance():

    # Make sure trigger starts LOW
    GPIO.output(TRIG, GPIO.LOW)
    sleep(0.000002)

    # 10 us trigger pulse
    GPIO.output(TRIG, GPIO.HIGH)
    sleep(0.00001)
    GPIO.output(TRIG, GPIO.LOW)

    # Wait for ECHO to go HIGH
    timeout = time() + 0.03

    while GPIO.input(ECHO) == 0:
        if time() > timeout:
            return None

    start = time()

    # Wait for ECHO to go LOW
    timeout = time() + 0.03

    while GPIO.input(ECHO) == 1:
        if time() > timeout:
            return None

    end = time()

    distance = (end - start) * 34300 / 2

    if distance < 2 or distance > 400:
        return None

    return distance


# ============================================================
# SCAN
# ============================================================

POSITIONS = [
    ("LEFT", -1.0),
    ("CENTER", 0.0),
    ("RIGHT", 1.0),
]


try:

    print()
    print("==============================================")
    print("       FIREBOT ULTRASONIC SCANNER")
    print("==============================================")
    print()
    print("TRIG  : GPIO 16 (Physical 36)")
    print("ECHO  : GPIO 20 (Physical 38)")
    print("SERVO : GPIO 26 (Physical 37)")
    print()
    print("Press CTRL+C to stop.")
    print()

    scanner.value = 0
    sleep(1)

    while True:

        for name, position in POSITIONS:

            scanner.value = position
            sleep(0.5)

            readings = []

            for _ in range(3):

                distance = get_distance()

                if distance is not None:
                    readings.append(distance)

                sleep(0.1)

            if readings:

                average = sum(readings) / len(readings)

                print(
                    f"{name:6s} | "
                    f"{average:6.1f} cm | "
                    f"readings: {len(readings)}/3"
                )

            else:

                print(
                    f"{name:6s} | "
                    f"NO ECHO"
                )

        print("----------------------------------------------")


except KeyboardInterrupt:

    print("\nStopping scanner...")


finally:

    scanner.value = 0
    sleep(0.3)
    scanner.detach()

    GPIO.output(TRIG, GPIO.LOW)
    GPIO.cleanup()

    print("Scanner stopped.")
