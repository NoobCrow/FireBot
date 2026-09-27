"""
servo_calibrate.py

Interactive tool to find the real usable angle range and center
position of a servo wired straight to a Pi GPIO pin.

Controls:
a / d   -> decrease / increase angle by 1 degree
A / D   -> decrease / increase angle by 10 degrees
c       -> print current angle (mark this down as your center)
q       -> quit

Run this once per servo.
Change SERVO_PIN below for the other servo.
"""

from gpiozero import AngularServo
import sys
import termios
import tty

try:
    from gpiozero.pins.pigpio import PiGPIOFactory

    PIN_FACTORY = PiGPIOFactory()
    print("Using pigpio.")
except Exception:
    PIN_FACTORY = None
    print("pigpio daemon not found - using plain GPIO software PWM.")


SERVO_PIN = 18  # Change to 19 for the other servo


servo = AngularServo(
    SERVO_PIN,
    min_angle=0,
    max_angle=180,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=PIN_FACTORY,
)


angle = 90

# AngularServo is centered around 0
servo.angle = angle 


def read_key():
    """Read a single keypress without needing Enter."""
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

    # Keep the original 0-180 calibration range
    new_angle = max(0, min(180, new_angle))

    angle = new_angle
    servo.angle = angle 

    print(f"angle = {angle}")


print()
print("========================================")
print("       SERVO CALIBRATION TOOL")
print("========================================")
print(f"GPIO pin: {SERVO_PIN}")
print(f"Starting angle: {angle}")
print()
print("Controls:")
print("a / d = -1 / +1 degree")
print("A / D = -10 / +10 degrees")
print("c     = mark current position as CENTER")
print("q     = quit")
print()
print("Move slowly and observe the servo.")
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
            print(f">>> CENTER = {angle} degrees")
            print(f">>> GPIO{SERVO_PIN}")
            print()


finally:
    servo.detach()

    print()
    print(f"Done. Final angle was {angle} on GPIO{SERVO_PIN}.")
    print("Repeat with SERVO_PIN changed to calibrate the other servo.")
