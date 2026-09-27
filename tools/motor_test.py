import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ============================================================
# MOTOR GPIO PINS
# ============================================================

MOTORS = {
    "M1": (17, 27),
    "M2": (22, 23),
    "M3": (24, 25),
    "M4": (5, 6),
}

# ============================================================
# MOTOR DIRECTION
# ============================================================
# True  = reverse the motor direction
# False = normal motor direction

REVERSED = {
    "M1": True,
    "M2": True,
    "M3": False,
    "M4": False,
}

# ============================================================
# GPIO SETUP
# ============================================================

for in1, in2 in MOTORS.values():
    GPIO.setup(in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(in2, GPIO.OUT, initial=GPIO.LOW)


# ============================================================
# MOTOR FUNCTIONS
# ============================================================

def stop_motor(motor):
    in1, in2 = MOTORS[motor]

    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.LOW)


def forward(motor):
    in1, in2 = MOTORS[motor]

    if REVERSED[motor]:
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)
    else:
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)


def reverse(motor):
    in1, in2 = MOTORS[motor]

    if REVERSED[motor]:
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)
    else:
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)


def stop_all():
    for motor in MOTORS:
        stop_motor(motor)


# ============================================================
# TEST
# ============================================================

try:

    print("\n================================")
    print("       FIREBOT MOTOR TEST")
    print("================================")

    print("\nDirection settings:")

    for motor in MOTORS:
        print(f"{motor}: REVERSED = {REVERSED[motor]}")

    print("\nEach motor will run:")
    print("FORWARD -> STOP -> REVERSE -> STOP")

    for motor in ["M1", "M2", "M3", "M4"]:

        stop_all()

        print(f"\n----- {motor} -----")

        input(f"Press ENTER to test {motor}...")

        print(f"{motor}: FORWARD")
        forward(motor)
        time.sleep(2)

        print(f"{motor}: STOP")
        stop_motor(motor)
        time.sleep(1)

        print(f"{motor}: REVERSE")
        reverse(motor)
        time.sleep(2)

        print(f"{motor}: STOP")
        stop_motor(motor)
        time.sleep(1)

        print(f"{motor}: COMPLETE")

    print("\n================================")
    print("ALL MOTOR TESTS COMPLETE")
    print("================================")

except KeyboardInterrupt:

    print("\nEMERGENCY STOP!")

finally:

    stop_all()
    GPIO.cleanup()

    print("All motors stopped.")
