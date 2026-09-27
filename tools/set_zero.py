"""
servo_calibrate.py

Interactive servo calibration tool.

Controls:
a / d   -> decrease / increase by 1 degree
A / D   -> decrease / increase by 10 degrees
c       -> mark current position as center
q       -> quit

Run once for each servo.
Change SERVO_PIN below.
"""

from gpiozero import AngularServo
import sys
import termios
import tty

# Try pigpio first
try:
    from gpiozero.pins.pigpio import PiGPIOFactory

    PIN_FACTORY = PiGPIOFactory()
    print("Using pigpio.")
except Exception:
    PIN_FACTORY = None
    print("pigpio daemon not found - using plain GPIO software PWM.")


# ============================================================
# CHANGE THIS FOR THE OTHER SERVO
# ============================================================

SERVO_PIN = 18

# ============================================================


servo = AngularServo(
    SERVO_PIN,
    min_angle=-180,
    max_angle=180,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=PIN_FACTORY,
)

# Start at 90 degrees
angle = 90

servo.angle = angle - 90


def read_key():
    """Read one key without pressing Enter."""
    fd = sys.stdin.fileno()

    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return ch


def set_angle(new_angle):
    global angle

    angle = new_angle

    # Convert our calibration angle to AngularServo's coordinate system
    servo.angle = angle - 90

    print(f"angle = {angle}")


print()
print("========================================")
print("       SERVO CALIBRATION TOOL")
print("========================================")
print(f"GPIO pin : {SERVO_PIN}")
print(f"Starting : {angle} degrees")
print()
print("Controls:")
print("  a = -1 degree")
print("  d = +1 degree")
print("  A = -10 degrees")
print("  D = +10 degrees")
print("  c = mark current position as CENTER")
print("  q = quit")
print()
print("Move slowly and watch the mechanism.")
print("Record the point where it reaches its real mechanical limit.")
print("========================================")
print()


try:

    while True:

        key = read_key()

        if key == "q":
            break

        elif key == "a":
            set_angle(angle - 1)

        elif key == "d":
            set_angle(angle + 1)

        elif key == "A":
            set_angle(angle - 10)

        elif key == "D":
            set_angle(angle + 10)

        elif key == "c":
            print()
            print("========================================")
            print(f"CENTER = {angle} degrees")
            print(f"GPIO    = {SERVO_PIN}")
            print("========================================")
            print()


finally:

    servo.detach()

    print()
    print("========================================")
    print("Calibration finished.")
    print(f"GPIO      : {SERVO_PIN}")
    print(f"Final angle: {angle}")
    print("========================================")
