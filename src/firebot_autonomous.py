import cv2
import time
import RPi.GPIO as GPIO

from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from picamera2 import Picamera2

from detect import detect


# ============================================================
# SERVO SETUP
# ============================================================

factory = PiGPIOFactory()

pan_servo = Servo(16, min_pulse_width=0.5 / 1000, max_pulse_width=2.5 / 1000, pin_factory=factory)
tilt_servo = Servo(10, min_pulse_width=0.5 / 1000, max_pulse_width=2.5 / 1000, pin_factory=factory)
hose_servo = Servo(13, min_pulse_width=0.5 / 1000, max_pulse_width=2.5 / 1000, pin_factory=factory)


# ============================================================
# HOSE SERVO
# ============================================================

HOSE_SERVO_MIN = -1.0
HOSE_SERVO_CENTER = 0.0
HOSE_SERVO_MAX = 1.0

hose_servo.value = HOSE_SERVO_CENTER
time.sleep(1)


# ============================================================
# GPIO
# ============================================================

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


# ============================================================
# PUMP
# ============================================================

RELAY_PIN = 9
RELAY_ACTIVE_LOW = False

GPIO.setup(RELAY_PIN, GPIO.OUT)


def pump_on():
    GPIO.output(RELAY_PIN, GPIO.LOW if RELAY_ACTIVE_LOW else GPIO.HIGH)


def pump_off():
    GPIO.output(RELAY_PIN, GPIO.HIGH if RELAY_ACTIVE_LOW else GPIO.LOW)


pump_off()


# ============================================================
# MOTOR CONFIGURATION
# ============================================================

MOTORS = {
    "M1": (17, 27),
    "M2": (22, 23),
    "M3": (24, 25),
    "M4": (5, 6),
}

ENABLE = {
    "M1": 14,
    "M2": 18,
    "M3": 4,
    "M4": 19,
}

REVERSED = {
    "M1": True,
    "M2": True,
    "M3": True,
    "M4": False,
}


# ============================================================
# FORWARD MOTOR SPEEDS
# ============================================================

SPEED = {
    "M1": 55,
    "M2": 55,
    "M3": 90,
    "M4": 65,
}

PWM_FREQUENCY = 1000


# ============================================================
# MOTOR INITIALIZATION
# ============================================================

for motor in MOTORS:
    in1, in2 = MOTORS[motor]
    GPIO.setup(in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(in2, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(ENABLE[motor], GPIO.OUT, initial=GPIO.LOW)

pwm = {}

for motor in MOTORS:
    pwm[motor] = GPIO.PWM(ENABLE[motor], PWM_FREQUENCY)
    pwm[motor].start(0)


# ============================================================
# MOTOR FUNCTIONS
# ============================================================

def stop_motor(motor):
    in1, in2 = MOTORS[motor]
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.LOW)
    pwm[motor].ChangeDutyCycle(0)


def stop_all():
    for motor in MOTORS:
        stop_motor(motor)


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


# ============================================================
# MOVEMENT TUNING
# ============================================================

# Forward movement (was 0.15)
FORWARD_PULSE_TIME = 0.18

# ------------------------------------------------------------
# LEFT / RIGHT
# ------------------------------------------------------------
# Steering needs 100% power because of static friction.
# Steering aggressiveness is controlled by TIME, not duty.

# Right steer (was 0.05)
STEER_PULSE_TIME = 0.06

# Left steer (was 0.07) — reduced, left was overshooting
STEER_PULSE_TIME_LEFT = 0.065

# Steering power
STEER_FULL_POWER_DUTY = 100

# Delay when changing direction
DIRECTION_CHANGE_DELAY = 0.10


# ============================================================
# DRIVE PULSE
# ============================================================

def drive_pulse(direction, duration, speed_scale=1.0):

    # Stop first
    stop_all()
    time.sleep(DIRECTION_CHANGE_DELAY)

    if direction == "forward":
        forward("M1")
        forward("M2")
        forward("M3")
        forward("M4")

    elif direction == "reverse":
        reverse("M1")
        reverse("M2")
        reverse("M3")
        reverse("M4")

    elif direction == "left":
        reverse("M1")
        reverse("M2")
        forward("M3")
        forward("M4")

    elif direction == "right":
        forward("M1")
        forward("M2")
        reverse("M3")
        reverse("M4")

    else:
        stop_all()
        return

    # PWM
    if direction in ("left", "right"):
        # Steering = 100%
        for motor in MOTORS:
            pwm[motor].ChangeDutyCycle(STEER_FULL_POWER_DUTY)
    else:
        # Forward / reverse
        for motor in MOTORS:
            pwm[motor].ChangeDutyCycle(SPEED[motor] * speed_scale)

    # Run
    time.sleep(duration)
    stop_all()


# ============================================================
# CAMERA
# ============================================================

print("Starting camera...")

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)

picam2.configure(config)
picam2.start()
time.sleep(2)

print("Camera started.")

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

CENTER_X = FRAME_WIDTH // 2
CENTER_Y = FRAME_HEIGHT // 2


# ============================================================
# TRACKING SETTINGS
# ============================================================

PAN_STEP = 0.02
TILT_STEP = 0.02

CENTER_TOLERANCE_X = 40

# Fire may appear lower in the image at close range.
CENTER_TOLERANCE_Y = 120

TRACK_DELAY = 0.08

NO_FIRE_LIMIT = 15


# ============================================================
# PAN LIMITS
# ============================================================

PAN_MIN = -0.50
PAN_MAX = 1.00


# ============================================================
# TILT LIMITS
# ============================================================

TILT_LOGICAL_MIN = -0.20
TILT_LOGICAL_MAX = 0.70


# ============================================================
# SEARCH
# ============================================================

SCAN_TIME = 5.0

SERVO_SETTLE_TIME = 0.30


# ============================================================
# TILT CONVERSION
# ============================================================

def tilt_to_servo(logical_value):
    logical_value = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, logical_value))
    normalized = (logical_value - TILT_LOGICAL_MIN) / (TILT_LOGICAL_MAX - TILT_LOGICAL_MIN)
    return -1.0 + normalized * 2.0


# ============================================================
# CURRENT SERVO POSITIONS
# ============================================================

current_pan = 1.00
current_tilt = 0.40


# ============================================================
# PAN
# ============================================================

def move_pan(value):
    global current_pan
    value = max(PAN_MIN, min(PAN_MAX, value))
    pan_servo.value = value
    time.sleep(SERVO_SETTLE_TIME)
    current_pan = value


# ============================================================
# TILT
# ============================================================

def move_tilt(logical_value):
    global current_tilt
    logical_value = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, logical_value))
    tilt_servo.value = tilt_to_servo(logical_value)
    time.sleep(SERVO_SETTLE_TIME)
    current_tilt = logical_value


# ============================================================
# HOSE
# ============================================================

HOSE_SETTLE_TIME = 0.05

HOSE_SWEEP_STEP = 0.20

HOSE_FORWARD = 0

HOSE_LEFT_OFFSET = 1.0
HOSE_RIGHT_OFFSET = 0.4

HOSE_SWEEP_MIN = HOSE_FORWARD - HOSE_LEFT_OFFSET
HOSE_SWEEP_MAX = HOSE_FORWARD + HOSE_RIGHT_OFFSET

current_hose = HOSE_FORWARD


# ============================================================
# HOSE MOVEMENT
# ============================================================

def move_hose(value):
    global current_hose
    value = max(HOSE_SERVO_MIN, min(HOSE_SERVO_MAX, value))
    hose_servo.value = value
    time.sleep(HOSE_SETTLE_TIME)
    current_hose = value


# ============================================================
# APPROACH / SPRAY
# ============================================================

# Fire is "close" when its bounding box is this wide.
# Larger value = robot drives closer before spraying. (was 400)
FIRE_CLOSE_BOX_WIDTH_PX = 450

# Confirm centered fire for 3 frames.
SPRAY_TRIGGER_CONFIRM_FRAMES = 3

# Number of spray epochs.
SPRAY_EPOCHS = 20

# Straight-ahead pan position.
PAN_FORWARD = 0.0

# If current_pan is within this range, no steering correction.
STEER_TOLERANCE = 0.25


# ============================================================
# SCAN POSITIONS
# ============================================================

SCAN_POSITIONS = [
    ("1/8", 1.00, 0.60),
    ("2/8", 0.50, 0.60),
    ("3/8", 0.10, 0.60),
    ("4/8", -0.60, 0.60),
    ("5/8", -0.50, 1.00),
    ("6/8", 0.10, 1.00),
    ("7/8", 0.60, 1.00),
    ("8/8", 1.00, 1.00),
]


# ============================================================
# HELPERS
# ============================================================

def show_and_check_quit(display):
    cv2.imshow("Fire Detection", display)
    key = cv2.waitKey(1) & 0xFF
    if key in (ord("q"), ord("Q")):
        raise KeyboardInterrupt


# ============================================================
# SEARCH FOR FIRE
# ============================================================

def search_for_fire():

    stop_all()
    pump_off()

    for i, (name, pan_value, tilt_value) in enumerate(SCAN_POSITIONS):

        print(f"\nSCAN {name} PAN={pan_value:.2f} TILT={tilt_value:.2f}")

        if pan_value != current_pan:
            move_pan(pan_value)

        if tilt_value != current_tilt:
            move_tilt(tilt_value)

        start_time = time.time()

        while time.time() - start_time < SCAN_TIME:

            frame = picam2.capture_array()
            display, detections = detect(frame)

            show_and_check_quit(display)

            if detections:
                print("FIRE DETECTED — switching to tracking.")
                return True

    return False


# ============================================================
# LOCAL REACQUIRE
# ============================================================

def local_reacquire():

    original_pan = current_pan
    original_tilt = current_tilt

    PAN_OFFSET = 0.15
    TILT_OFFSET = 0.10

    check_points = [
        ("LEFT-UP", original_pan + PAN_OFFSET, original_tilt + TILT_OFFSET),
        ("LEFT-DOWN", original_pan + PAN_OFFSET, original_tilt - TILT_OFFSET),
        ("RIGHT-UP", original_pan - PAN_OFFSET, original_tilt + TILT_OFFSET),
        ("RIGHT-DOWN", original_pan - PAN_OFFSET, original_tilt - TILT_OFFSET),
    ]

    print("Fire lost — checking 4-point grid...")

    for label, pan_candidate, tilt_candidate in check_points:

        pan_candidate = max(PAN_MIN, min(PAN_MAX, pan_candidate))
        tilt_candidate = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, tilt_candidate))

        move_pan(pan_candidate)
        move_tilt(tilt_candidate)

        frame = picam2.capture_array()
        display, detections = detect(frame)

        show_and_check_quit(display)

        if detections:
            print(f"Reacquired at {label}.")
            return True

    # Restore original position
    move_pan(original_pan)
    move_tilt(original_tilt)

    print("Local re-acquire failed. Falling back to full search.")

    return False


# ============================================================
# TRACK + APPROACH
# ============================================================

def track_and_approach():

    no_fire_count = 0
    spray_epoch_count = 0
    hose_sweep_direction = 1
    spray_confirm_count = 0
    is_spraying = False

    while True:

        # ====================================================
        # CAMERA
        # ====================================================

        frame = picam2.capture_array()
        display, detections = detect(frame)

        # ====================================================
        # NO FIRE
        # ====================================================

        if not detections:

            no_fire_count += 1

            print(f"No fire: {no_fire_count}/{NO_FIRE_LIMIT}")

            cv2.putText(display, f"NO FIRE {no_fire_count}/{NO_FIRE_LIMIT}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            if no_fire_count >= NO_FIRE_LIMIT:

                stop_all()
                pump_off()

                is_spraying = False
                spray_confirm_count = 0

                if local_reacquire():
                    no_fire_count = 0
                    time.sleep(TRACK_DELAY)
                    continue

                print("Fire lost. Returning to search.")
                return

            show_and_check_quit(display)
            time.sleep(TRACK_DELAY)
            continue

        # ====================================================
        # FIRE VISIBLE
        # ====================================================

        no_fire_count = 0

        target = max(detections, key=lambda d: d["confidence"])

        x1, y1, x2, y2 = target["box"]

        fire_center_x = int((x1 + x2) / 2)
        fire_center_y = int((y1 + y2) / 2)

        fire_box_width = x2 - x1

        error_x = fire_center_x - CENTER_X
        error_y = fire_center_y - CENTER_Y

        print(
            f"Fire@({fire_center_x},{fire_center_y})  "
            f"err=({error_x},{error_y})  "
            f"pan={current_pan:.2f}  "
            f"box_width={fire_box_width}px"
        )

        # ====================================================
        # CAMERA PAN TRACKING
        # ====================================================

        if abs(error_x) > CENTER_TOLERANCE_X:

            if error_x > CENTER_TOLERANCE_X:
                new_pan = current_pan - PAN_STEP
            else:
                new_pan = current_pan + PAN_STEP

            move_pan(new_pan)

        # ====================================================
        # CAMERA TILT TRACKING
        # ====================================================

        elif abs(error_y) > CENTER_TOLERANCE_Y:

            if error_y > CENTER_TOLERANCE_Y:
                new_tilt = current_tilt + TILT_STEP
            else:
                new_tilt = current_tilt - TILT_STEP

            move_tilt(new_tilt)

        # ====================================================
        # STATE CHECKS
        # ====================================================

        box_close_enough = fire_box_width >= FIRE_CLOSE_BOX_WIDTH_PX

        screen_centered = (
            abs(error_x) <= CENTER_TOLERANCE_X
            and abs(error_y) <= CENTER_TOLERANCE_Y
        )

        # ====================================================
        # FINAL BODY ALIGNMENT
        # ====================================================

        if box_close_enough:

            pan_error = current_pan - PAN_FORWARD

            if abs(pan_error) > STEER_TOLERANCE:

                print(f"Close to fire but body not aligned. pan={current_pan:.2f}")

                pump_off()
                stop_all()

                if pan_error > 0:
                    print(f"FINAL CORRECTION: LEFT 100% for {STEER_PULSE_TIME_LEFT}s")
                    drive_pulse("left", STEER_PULSE_TIME_LEFT)
                else:
                    print(f"FINAL CORRECTION: RIGHT 100% for {STEER_PULSE_TIME}s")
                    drive_pulse("right", STEER_PULSE_TIME)

                spray_confirm_count = 0
                continue

            # Body aligned
            if screen_centered:
                spray_confirm_count += 1
                print(f"SPRAY CONFIRM {spray_confirm_count}/{SPRAY_TRIGGER_CONFIRM_FRAMES}")
            else:
                spray_confirm_count = 0

        else:
            spray_confirm_count = 0

        # ====================================================
        # SPRAY DECISION
        # ====================================================

        ready_to_spray = (
            is_spraying
            or spray_confirm_count >= SPRAY_TRIGGER_CONFIRM_FRAMES
        )

        # ====================================================
        # SPRAYING
        # ====================================================

        if ready_to_spray:

            is_spraying = True
            spray_epoch_count += 1

            print(f"SPRAYING epoch={spray_epoch_count}/{SPRAY_EPOCHS} — tracking frozen")

            stop_all()
            pump_on()

            # Hose sweep
            new_hose = current_hose + HOSE_SWEEP_STEP * hose_sweep_direction

            if new_hose >= HOSE_SWEEP_MAX:
                new_hose = HOSE_SWEEP_MAX
                hose_sweep_direction = -1
            elif new_hose <= HOSE_SWEEP_MIN:
                new_hose = HOSE_SWEEP_MIN
                hose_sweep_direction = 1

            move_hose(new_hose)

            cv2.putText(display, f"SPRAYING {spray_epoch_count}/{SPRAY_EPOCHS}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            cv2.imshow("Fire Detection", display)
            cv2.waitKey(1)

            time.sleep(TRACK_DELAY)

            # Spray finished
            if spray_epoch_count >= SPRAY_EPOCHS:

                print("Spray done — pump off, resuming tracking.")

                pump_off()
                move_hose(HOSE_FORWARD)

                is_spraying = False
                spray_confirm_count = 0
                spray_epoch_count = 0
                hose_sweep_direction = 1

            continue

        # ====================================================
        # CLOSE BUT NOT READY
        # ====================================================

        elif box_close_enough:

            stop_all()
            pump_off()

            spray_epoch_count = 0
            is_spraying = False

            print(
                f"Close (box={fire_box_width}px) — waiting for center. "
                f"err=({error_x},{error_y})"
            )

            cv2.putText(display, f"HOLDING box={fire_box_width}px",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        # ====================================================
        # APPROACH
        # ====================================================

        else:

            pump_off()

            spray_epoch_count = 0
            is_spraying = False

            pan_error = current_pan - PAN_FORWARD

            if abs(pan_error) > STEER_TOLERANCE:

                if pan_error > 0:
                    print("STEERING LEFT 100% — short pulse")
                    drive_pulse("left", STEER_PULSE_TIME_LEFT)
                else:
                    print("STEERING RIGHT 100% — short pulse")
                    drive_pulse("right", STEER_PULSE_TIME)

            else:
                print("FORWARD — FAST")
                drive_pulse("forward", FORWARD_PULSE_TIME)

            cv2.putText(display, f"APPROACHING box={fire_box_width}px",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        # ====================================================
        # VISUALIZATION
        # ====================================================

        cv2.rectangle(
            display,
            (CENTER_X - CENTER_TOLERANCE_X, CENTER_Y - CENTER_TOLERANCE_Y),
            (CENTER_X + CENTER_TOLERANCE_X, CENTER_Y + CENTER_TOLERANCE_Y),
            (255, 200, 0),
            2
        )

        cv2.circle(display, (CENTER_X, CENTER_Y), 7, (255, 255, 255), -1)
        cv2.circle(display, (fire_center_x, fire_center_y), 7, (0, 255, 0), -1)
        cv2.line(display, (CENTER_X, CENTER_Y), (fire_center_x, fire_center_y), (0, 255, 0), 2)

        show_and_check_quit(display)

        time.sleep(TRACK_DELAY)


# ============================================================
# MAIN
# ============================================================

try:

    print()
    print("========================================")
    print("      FIREBOT — AUTONOMOUS SEEK & HOLD")
    print("========================================")
    print(f"Spray trigger: box>={FIRE_CLOSE_BOX_WIDTH_PX}px + screen centered + body aligned")
    print(f"CENTER_TOLERANCE: X={CENTER_TOLERANCE_X}px Y={CENTER_TOLERANCE_Y}px")
    print(f"PAN_FORWARD: {PAN_FORWARD}")
    print(f"STEER_TOLERANCE: {STEER_TOLERANCE}")
    print(f"FORWARD PULSE: {FORWARD_PULSE_TIME}s")
    print(f"RIGHT STEER: 100% / {STEER_PULSE_TIME}s")
    print(f"LEFT STEER: 100% / {STEER_PULSE_TIME_LEFT}s")
    print("========================================")

    while True:

        try:

            found = search_for_fire()

            if found:
                track_and_approach()
            else:
                print("Full sweep done, no fire. Sweeping again...")

        except KeyboardInterrupt:
            raise

        except Exception as e:
            print(f"[main loop] error, recovering: {e}")
            stop_all()
            pump_off()
            time.sleep(0.5)


# ============================================================
# SHUTDOWN
# ============================================================

except KeyboardInterrupt:
    print("\nStopping FireBot...")

finally:

    stop_all()
    pump_off()

    for motor in pwm:
        pwm[motor].stop()

    GPIO.cleanup()

    pan_servo.value = None
    tilt_servo.value = None
    hose_servo.value = None

    picam2.stop()
    cv2.destroyAllWindows()

    print("Stopped.")
