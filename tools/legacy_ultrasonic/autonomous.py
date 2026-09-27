import cv2
import time
import RPi.GPIO as GPIO

from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from picamera2 import Picamera2

from detect import detect


# ============================================================
# FIREBOT — AUTONOMOUS SEEK & HOLD
#
# Merge of:
#   1) pan_tilt_tracking.py  -> fire detection + camera aiming
#   2) motor_keyboard.py     -> drivetrain (converted to pulsed,
#                                non-blocking calls)
#
# Behaviour:
#   SEARCHING   -> pan/tilt sweeps a fixed set of positions
#                  looking for fire (same 8-position pattern as
#                  the original scan script)
#   TRACKING    -> fire is visible. Pan/tilt keeps it centered.
#                  If the robot's body is roughly aimed at the
#                  fire (pan near PAN_FORWARD) it creeps forward
#                  in short pulses. If the fire is off to a
#                  side, the body steers (turn_left/turn_right)
#                  instead of driving blind.
#   HOLDING     -> fire's bounding box in the camera frame is wide
#                  enough (FIRE_CLOSE_BOX_WIDTH_PX) AND the fire is
#                  currently centered on screen (within
#                  CENTER_TOLERANCE_X/Y) — vision only, no
#                  ultrasonic anywhere in this robot anymore.
#                  Motors stay stopped, pan/tilt keeps tracking.
#
# ------------------------------------------------------------
# FIX (this version): the spray trigger used to require the
# pan/tilt SERVO ANGLES to sit within +/-0.05 of a fixed
# "confirmed" value (PAN_SPRAY_TARGET / TILT_SPRAY_TARGET).
# Nothing in the tracking loop actually drives current_pan
# toward that fixed value though — pan/tilt only move to
# re-center the fire ON SCREEN, and current_pan settles
# wherever the approach angle happens to leave it (which
# varies run to run and is usually outside +/-0.05). Result:
# the box-width condition was satisfied constantly but the
# angle condition almost never was, so the robot never
# stopped/sprayed.
#
# Replaced that angle check with the thing we actually control
# precisely every frame: is the fire centered ON SCREEN right
# now (abs(error_x) <= CENTER_TOLERANCE_X and abs(error_y) <=
# CENTER_TOLERANCE_Y)? Combined with the box-width check, this
# is a more physically sound "robot is squared up and close"
# signal regardless of what particular servo angle that
# corresponds to on a given approach.
# ============================================================


# ============================================================
# PIN FACTORY (shared by gpiozero devices: servos)
# ============================================================

factory = PiGPIOFactory()


# ============================================================
# PAN / TILT SERVOS  (camera aiming)
# GPIO 12 = PAN   (Physical Pin 32)
# GPIO 13 = TILT  (Physical Pin 33)
# ============================================================

pan_servo = Servo(
    12,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)

tilt_servo = Servo(
    13,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)


# ============================================================
# HOSE-AIM SERVO
# GPIO 10 = Physical Pin 19
#
# FIXED: this was set to GPIO 26 (physical pin 37) — a pin the
# hose servo isn't actually wired to. Corrected to match the
# wiring confirmed by the standalone hose servo test script:
# BCM GPIO 10, which is physical header pin 19.
#
# This used to also carry the ultrasonic sensor for obstacle
# scanning — ultrasonic has been removed entirely, so this servo
# now exists purely to aim the water spray while HOLDING.
# ============================================================

hose_servo = Servo(
    10,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)

HOSE_SERVO_MIN = -1.0
HOSE_SERVO_CENTER = 0.0
HOSE_SERVO_MAX = 1.0

hose_servo.value = HOSE_SERVO_CENTER
time.sleep(1)


# ============================================================
# DRIVE MOTORS (RPi.GPIO, L298N drivers)
# ============================================================

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


# ============================================================
# PUMP RELAY
# GPIO 9 = Physical Pin 21
#
# FIXED: this was set to RELAY_PIN = 21 (BCM GPIO 21 / physical
# pin 40) — a pin your relay isn't actually wired to, which is
# why the pump would never turn on here even though the
# standalone pump_test.py (using GPIO 9 / physical pin 21)
# worked fine. Corrected to match the wiring: BCM GPIO 9, which
# is physical header pin 21.
# ============================================================

RELAY_PIN = 9

# Your relay: HIGH = ON, LOW = OFF
RELAY_ACTIVE_LOW = False

GPIO.setup(RELAY_PIN, GPIO.OUT)


def pump_on():
    if RELAY_ACTIVE_LOW:
        GPIO.output(RELAY_PIN, GPIO.LOW)
    else:
        GPIO.output(RELAY_PIN, GPIO.HIGH)


def pump_off():
    if RELAY_ACTIVE_LOW:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
    else:
        GPIO.output(RELAY_PIN, GPIO.LOW)


pump_off()

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
    "M3": False,
    "M4": False,
}

SPEED = {
    "M1": 55,
    "M2": 55,
    "M3": 90,
    "M4": 65,
}

PWM_FREQUENCY = 1000

for motor in MOTORS:
    in1, in2 = MOTORS[motor]
    GPIO.setup(in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(in2, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(ENABLE[motor], GPIO.OUT, initial=GPIO.LOW)

pwm = {}

for motor in MOTORS:
    pwm[motor] = GPIO.PWM(ENABLE[motor], PWM_FREQUENCY)
    pwm[motor].start(0)


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


def enable_motor(motor):
    # NOTE: not currently called anywhere — drive_pulse() sets duty
    # cycle directly on all four motors instead. Left in place in
    # case you want per-motor enable control later; harmless as-is.
    pwm[motor].ChangeDutyCycle(SPEED[motor])


DIRECTION_CHANGE_DELAY = 0.10

# How long each drive command runs before the loop re-checks
# vision. Short = more responsive, more jerky.
# Long = smoother, less reactive. Tune this on real hardware.
FORWARD_PULSE_TIME = 0.30
STEER_PULSE_TIME = 0.28

# The robot has a physical weakness turning left (mechanical, not
# fixable in software directly) — since steering is already at full
# power (STEER_FULL_POWER_DUTY), the only lever left to compensate
# is running the left pulse longer so it covers roughly the same
# real angle as a right turn does in STEER_PULSE_TIME. STARTING
# GUESS (1.5x) — tune on hardware: watch how far the robot actually
# turns left vs right and adjust until they roughly match.
STEER_PULSE_TIME_LEFT = 0.42

# Steering turns rotate the whole chassis, which swings the fire
# out of frame fast — that's why these were previously scaled
# down. Now using full hardware power (100% duty cycle on every
# motor) for steering per request, not just the calibrated SPEED
# values — SPEED[] are tuned for smooth forward driving, not
# necessarily the motors' actual max, so steering now bypasses
# them entirely to turn as fast/hard as the hardware allows.
STEER_FULL_POWER_DUTY = 100


def drive_pulse(direction, duration, speed_scale=1.0):
    """
    Run the drivetrain in `direction` for `duration` seconds,
    then stop. Pulsed (rather than the original's blocking
    drive_forward/drive_reverse) so the control loop can
    re-check the camera every cycle
    instead of driving blind for 2 full seconds.

    direction: "forward", "reverse", "left", "right", or None/"stop"
    speed_scale: multiplies each motor's calibrated SPEED value
                 for "forward"/"reverse" pulses only (SPEED dict
                 itself is never modified). Use < 1.0 for gentler
                 driving. Ignored for "left"/"right" — steering
                 always runs at STEER_FULL_POWER_DUTY instead.
    """

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

    if direction in ("left", "right"):
        for motor in MOTORS:
            pwm[motor].ChangeDutyCycle(STEER_FULL_POWER_DUTY)
    else:
        for motor in MOTORS:
            pwm[motor].ChangeDutyCycle(SPEED[motor] * speed_scale)

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
# TRACKING SETTINGS (from script 1)
# ============================================================

PAN_STEP = 0.02
TILT_STEP = 0.02

CENTER_TOLERANCE_X = 40
CENTER_TOLERANCE_Y = 40

TRACK_DELAY = 0.08

NO_FIRE_LIMIT = 15

PAN_MIN = -0.50
PAN_MAX = 1.00

TILT_LOGICAL_MIN = -0.20
TILT_LOGICAL_MAX = 0.70

SCAN_TIME = 5.0
SERVO_SETTLE_TIME = 0.30


def tilt_to_servo(logical_value):
    logical_value = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, logical_value))
    normalized = (logical_value - TILT_LOGICAL_MIN) / (TILT_LOGICAL_MAX - TILT_LOGICAL_MIN)
    return -1.0 + (normalized * 2.0)


current_pan = 1.00
current_tilt = 0.40


def move_pan(value):
    global current_pan
    value = max(PAN_MIN, min(PAN_MAX, value))
    pan_servo.value = value
    time.sleep(SERVO_SETTLE_TIME)
    current_pan = value


def move_tilt(logical_value):
    global current_tilt
    logical_value = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, logical_value))
    tilt_servo.value = tilt_to_servo(logical_value)
    time.sleep(SERVO_SETTLE_TIME)
    current_tilt = logical_value


# ============================================================
# HOSE AIM (drives hose_servo / GPIO 10 — only used while HOLDING)
# ============================================================

HOSE_STEP = 0.02
HOSE_SETTLE_TIME = 0.05

# While spraying, the hose sweeps LEFT<->RIGHT across its full
# range instead of just holding on the fire's exact position, so
# the water spreads across a wider area.
#
# Bumped up alongside the wider HOSE_LEFT_OFFSET/HOSE_RIGHT_OFFSET
# below so the sweep still cycles end-to-end in a similar number
# of frames rather than crawling across the now much larger range.
HOSE_SWEEP_STEP = 0.20

# HOSE VALUE THAT ACTUALLY POINTS THE NOZZLE AT A CENTERED FIRE.
#
# The hose rides on hose_servo, a physically separate servo
# from the pan/tilt camera mount — so HOSE_SERVO_CENTER (0.0) is
# NOT guaranteed to line up with where the camera sees the fire
# centered. If the spray consistently lands off to one side,
# that's this offset needing calibration, not a code bug: aim
# the camera dead-center on a stationary flame, then manually
# move the hose servo until the water actually lands on it, and
# read off that value here.
#
# Starting guess nudged slightly left since testing showed spray
# landing right of target — adjust further based on what you see.
HOSE_FORWARD = 0

# How far LEFT and RIGHT of HOSE_FORWARD the sweep reaches.
# Separate values (not a single symmetric radius) since the
# mount may not be centered evenly — calibrate each side on its
# own by watching where the water actually lands.
#
# WIDENED on request: sweep now spans the servo's full physical
# range (HOSE_SERVO_MIN to HOSE_SERVO_MAX) instead of a narrow
# slice, so the spray covers much more ground side-to-side.
# HOSE_FORWARD=0 is centered between HOSE_SERVO_MIN(-1.0) and
# HOSE_SERVO_MAX(1.0), so an offset of 1.0 on each side reaches
# both physical ends. If the hose mount isn't evenly centered
# and one side clips/binds mechanically before reaching its
# offset, back that one side off — these don't have to match.
HOSE_LEFT_OFFSET = 1.0
HOSE_RIGHT_OFFSET = 1.0

HOSE_SWEEP_MIN = HOSE_FORWARD - HOSE_LEFT_OFFSET
HOSE_SWEEP_MAX = HOSE_FORWARD + HOSE_RIGHT_OFFSET

current_hose = HOSE_FORWARD


def move_hose(value):
    global current_hose
    value = max(HOSE_SERVO_MIN, min(HOSE_SERVO_MAX, value))
    hose_servo.value = value
    time.sleep(HOSE_SETTLE_TIME)
    current_hose = value


# ============================================================
# APPROACH / HOLD-TO-SPRAY SETTINGS
# ============================================================

# There is no ultrasonic sensor on this robot anymore — "how close
# am I to the fire" comes entirely from the fire's bounding box
# width in the camera frame: the box gets wider as the robot gets
# closer, so once it crosses this pixel width the robot stops
# driving forward and moves on to ALIGNING (see below).
#
# STARTING GUESS — needs calibration on real hardware: place the
# fire at the distance you actually want the robot to stop and
# spray from, read the box width printed in the console log at
# that distance, and set this value to match.
#
# LOWERED from 400 on request: the robot was driving too close
# to the fire before this gate tripped. Box width grows as the
# robot gets nearer, so a SMALLER threshold here makes the robot
# stop FARTHER away (it trips sooner, at an earlier/smaller box
# width); a LARGER threshold lets it get closer before stopping.
# 350 is only a new starting guess — walk the robot toward a
# stationary flame, watch the "box_width=...px" value printed
# each frame in the console, and set this to whatever width
# corresponds to the actual distance you want it to stop at.
FIRE_CLOSE_BOX_WIDTH_PX = 350

# ------------------------------------------------------------
# SPRAY TRIGGER — THREE PHASES
#
# APPROACH  -> box_width < FIRE_CLOSE_BOX_WIDTH_PX. Camera keeps
#              the fire centered on screen; body steers/drives
#              forward as before.
#
# ALIGNING  -> box_width >= FIRE_CLOSE_BOX_WIDTH_PX (close enough
#              on distance) but the body isn't squared up at the
#              confirmed spray angle yet. Camera still keeps the
#              fire centered on screen every frame. Forward
#              driving stops; instead the body takes small
#              steering nudges (ALIGN_STEER_PULSE_TIME(_LEFT),
#              much shorter than the approach-phase steer pulses)
#              to walk current_pan toward PAN_SPRAY_TARGET. This
#              is what actually makes the pan/tilt "reach" a
#              specific position — earlier versions checked pan
#              against a fixed target without anything ever
#              driving it there, so the check almost never passed.
#              Tilt isn't independently drivable by the chassis;
#              it's expected to already sit near TILT_SPRAY_TARGET
#              once the robot is at the right distance and pan is
#              aligned (confirmed on hardware), so it's checked but
#              not separately corrected.
#
# HOLDING   -> box still close AND pan/tilt both within tolerance
#              of the spray targets. Motors stop, pump turns on.
# ------------------------------------------------------------

# The pan/tilt position the camera should settle at once the body
# is properly squared up on the fire at spray distance.
#
# TILT_SPRAY_TARGET updated 0.40 -> 0.70 based on hardware logs:
# at box_width ~450-480px with pan aligned near 0.0, tilt was
# observed pinned at TILT_LOGICAL_MAX (0.70) frame after frame —
# the camera has to tilt all the way down to keep a close, low
# fire in frame, it never settles near 0.40. The old 0.40 value
# was simply wrong for this rig, which is why alignment used to
# hang indefinitely waiting on tilt.
PAN_SPRAY_TARGET = 0.0
TILT_SPRAY_TARGET = 0.70

# How far pan/tilt can be from the targets above and still count
# as "aligned". Tune based on how precisely pan/tilt actually
# settle in practice.
PAN_SPRAY_TOLERANCE = 0.05
TILT_SPRAY_TOLERANCE = 0.05

# Steering pulse durations used ONLY while ALIGNING (i.e. already
# close, just squaring up the body). Deliberately much shorter
# than the approach-phase STEER_PULSE_TIME(_LEFT) below, since at
# this range a full steering pulse would swing the fire out of
# frame or overshoot the target — these are meant to be small,
# repeated nudges. Same left/right asymmetry ratio as the
# approach pulses (robot turns weaker to the left) carried over;
# retune independently on hardware since the required nudge size
# may differ from the approach-phase turn.
ALIGN_STEER_PULSE_TIME = 0.12
ALIGN_STEER_PULSE_TIME_LEFT = 0.18

# How many consecutive frames the "close + aligned" condition
# must hold before committing to spray — guards against a single
# noisy detection frame flickering the trigger on and off.
SPRAY_TRIGGER_CONFIRM_FRAMES = 3

# How many loop cycles ("epochs") the pump stays on while
# HOLDING before shutting off and returning to search, treating
# the fire as extinguished.
SPRAY_EPOCHS = 20

# PAN VALUE THAT POINTS THE CHASSIS "STRAIGHT AHEAD".
#
# Updated from 0.25 -> 0.0 on request: the body was steering
# toward 0.25 while tracking, not actually squaring up with the
# fire. If the chassis is not physically dead-center at pan=0.0,
# this may need re-checking on hardware (point the robot straight
# ahead, move the pan servo until the camera also points straight
# ahead, and read off current_pan — that's the true value).
PAN_FORWARD = 0.0

# How far current_pan can drift from PAN_FORWARD before the
# robot steers its body instead of just driving forward.
#
# Widened from 0.15 -> 0.35 on request: the old value was
# re-triggering a steer correction almost every loop, so the
# robot spent most of its time nudging left/right instead of
# actually driving forward. This value is a starting guess for
# "mostly forward, steer rarely" — tune on hardware: if the body
# still drifts too far off-target before correcting, bring it
# back down a bit; if it's still steering too often, widen more.
STEER_TOLERANCE = 0.35


# ============================================================
# SCAN POSITIONS (unchanged from script 1 — used while SEARCHING)
# ============================================================

SCAN_POSITIONS = [
    ("1/8", 1.00, 0.60),
    ("2/8", 0.50, 0.60),
    ("3/8", 0.10, 0.60),
    ("4/8", -0.60, 0.60),
    # tilt change happens between 4 and 5, handled in the loop
    ("5/8", -0.50, 1),
    ("6/8", 0.10, 1),
    ("7/8", 0.60, 1),
    ("8/8", 1.00, 1),
]


def search_for_fire():
    """
    Sweep the 8 pan/tilt positions from script 1. Robot stays
    stationary (motors stopped) while searching. Returns True
    the moment fire is seen, leaving the camera roughly aimed
    at it so tracking can take over immediately.
    """

    stop_all()
    pump_off()

    for i, (name, pan_value, tilt_value) in enumerate(SCAN_POSITIONS):

        print(f"\nSCAN {name}  PAN={pan_value:.2f}  TILT={tilt_value:.2f}")

        if pan_value != current_pan:
            move_pan(pan_value)

        if tilt_value != current_tilt:
            move_tilt(tilt_value)

        start_time = time.time()

        while time.time() - start_time < SCAN_TIME:

            frame = picam2.capture_array()
            display, detections = detect(frame)

            cv2.imshow("Fire Detection", display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                raise KeyboardInterrupt

            if detections:
                print("🔥 FIRE DETECTED during search — switching to tracking/approach.")
                return True

    return False


def local_reacquire():
    """
    Fire just dropped out of frame — most likely because a steer
    pulse rotated the chassis (and camera) past it, not because
    it's actually gone. Instead of jumping straight to the full
    8-position search, check a small 4-point grid around the last
    known aim: LEFT and RIGHT of the last pan position, each
    checked at two tilt heights (up/down) — since the fire could
    have drifted out of frame vertically as well as horizontally.
    Returns True if fire is spotted again (camera is left aimed
    at it), False if nothing turns up nearby.
    """

    global current_pan, current_tilt

    original_pan = current_pan
    original_tilt = current_tilt

    PAN_OFFSET = 0.15
    TILT_OFFSET = 0.10

    check_points = [
        ("LEFT-UP",    original_pan + PAN_OFFSET, original_tilt + TILT_OFFSET),
        ("LEFT-DOWN",  original_pan + PAN_OFFSET, original_tilt - TILT_OFFSET),
        ("RIGHT-UP",   original_pan - PAN_OFFSET, original_tilt + TILT_OFFSET),
        ("RIGHT-DOWN", original_pan - PAN_OFFSET, original_tilt - TILT_OFFSET),
    ]

    print("Fire lost mid-approach — checking 4-point grid before full search...")

    for label, pan_candidate, tilt_candidate in check_points:

        pan_candidate = max(PAN_MIN, min(PAN_MAX, pan_candidate))
        tilt_candidate = max(TILT_LOGICAL_MIN, min(TILT_LOGICAL_MAX, tilt_candidate))

        move_pan(pan_candidate)
        move_tilt(tilt_candidate)

        frame = picam2.capture_array()
        display, detections = detect(frame)

        cv2.imshow("Fire Detection", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            raise KeyboardInterrupt

        if detections:
            print(f"Reacquired fire at {label} check point.")
            return True

    move_pan(original_pan)
    move_tilt(original_tilt)
    print("Local re-acquire failed. Falling back to full search.")
    return False


# ============================================================
# TRACK + APPROACH  (the merged behaviour)
# ============================================================

def track_and_approach():
    """
    Fire is visible. Pan/tilt keeps it centered every frame. If the
    robot's body is roughly aimed at the fire (pan near PAN_FORWARD)
    it creeps forward in short pulses — vision only, no obstacle
    sensor of any kind on this robot. If the fire is off to a side,
    the body steers instead of driving blind.

    "Reached the fire" is decided entirely from the camera, in
    three phases (see the SPRAY TRIGGER note near
    FIRE_CLOSE_BOX_WIDTH_PX above for the full rationale):

      APPROACH  box_width < FIRE_CLOSE_BOX_WIDTH_PX
                -> steer/drive forward as before.

      ALIGNING  box_width >= FIRE_CLOSE_BOX_WIDTH_PX but pan/tilt
                aren't yet within tolerance of PAN_SPRAY_TARGET /
                TILT_SPRAY_TARGET
                -> stop driving forward, take small steering
                   nudges to actively walk current_pan toward
                   PAN_SPRAY_TARGET while the camera keeps
                   centering the fire on screen.

      HOLDING   box_width >= FIRE_CLOSE_BOX_WIDTH_PX AND pan/tilt
                are within tolerance of the spray targets
                -> motors stop, pump on.

    The HOLDING condition must hold for SPRAY_TRIGGER_CONFIRM_FRAMES
    consecutive frames before spraying actually starts, to avoid a
    single noisy detection frame flickering the trigger.

    Returns when fire is lost (so the caller goes back to
    search_for_fire()).
    """

    no_fire_count = 0
    spray_epoch_count = 0
    hose_sweep_direction = 1
    spray_confirm_count = 0
    is_spraying = False

    while True:

        frame = picam2.capture_array()
        display, detections = detect(frame)

        # --------------------------------------------------
        # NO FIRE THIS FRAME
        # --------------------------------------------------
        if not detections:

            no_fire_count += 1
            print(f"No fire: {no_fire_count}/{NO_FIRE_LIMIT}")

            cv2.putText(
                display, f"NO FIRE {no_fire_count}/{NO_FIRE_LIMIT}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2
            )

            if no_fire_count >= NO_FIRE_LIMIT:

                stop_all()
                pump_off()
                is_spraying = False
                spray_confirm_count = 0

                if local_reacquire():
                    no_fire_count = 0
                    time.sleep(TRACK_DELAY)
                    continue

                print("Fire lost. Stopping motors, returning to search.")
                return

            cv2.imshow("Fire Detection", display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                raise KeyboardInterrupt

            time.sleep(TRACK_DELAY)
            continue

        # --------------------------------------------------
        # FIRE VISIBLE
        # --------------------------------------------------
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
            f"pan={current_pan:.2f}  box_width={fire_box_width}px"
        )

        # --------------------------------------------------
        # 1) KEEP CAMERA CENTERED ON FIRE (pan has priority,
        #    same rule as the original tracking_mode)
        # --------------------------------------------------
        if abs(error_x) > CENTER_TOLERANCE_X:

            if error_x > CENTER_TOLERANCE_X:
                new_pan = current_pan - PAN_STEP   # fire right -> pan left
            else:
                new_pan = current_pan + PAN_STEP   # fire left -> pan right

            move_pan(new_pan)

        elif abs(error_y) > CENTER_TOLERANCE_Y:

            if error_y > CENTER_TOLERANCE_Y:
                new_tilt = current_tilt + TILT_STEP  # fire below -> tilt up
            else:
                new_tilt = current_tilt - TILT_STEP  # fire above -> tilt down

            move_tilt(new_tilt)

        # --------------------------------------------------
        # 2) DRIVE DECISION — "reached fire" comes from the camera,
        #    not the ultrasonic sensor, in three phases:
        #      a) box wide enough at all? (close, roughly)
        #      b) if so, is the body actually squared up at the
        #         confirmed spray angle (pan/tilt within tolerance
        #         of PAN_SPRAY_TARGET/TILT_SPRAY_TARGET)? If not,
        #         ALIGN instead of driving forward or approach-
        #         steering.
        #      c) only once both agree do we HOLD + SPRAY.
        # --------------------------------------------------
        box_close_enough = fire_box_width >= FIRE_CLOSE_BOX_WIDTH_PX

        pan_error_from_target = current_pan - PAN_SPRAY_TARGET
        tilt_error_from_target = current_tilt - TILT_SPRAY_TARGET
        pan_aligned = abs(pan_error_from_target) <= PAN_SPRAY_TOLERANCE
        tilt_aligned = abs(tilt_error_from_target) <= TILT_SPRAY_TOLERANCE

        if box_close_enough and pan_aligned and tilt_aligned:
            spray_confirm_count += 1
        else:
            spray_confirm_count = 0

        ready_to_spray = is_spraying or (spray_confirm_count >= SPRAY_TRIGGER_CONFIRM_FRAMES)

        if ready_to_spray:

            is_spraying = True
            spray_epoch_count += 1

            print(
                f"✓ Fire box width {fire_box_width}px >= {FIRE_CLOSE_BOX_WIDTH_PX}px, "
                f"pan={current_pan:.2f}~{PAN_SPRAY_TARGET}, tilt={current_tilt:.2f}~{TILT_SPRAY_TARGET}. "
                f"HOLDING + SPRAYING ({spray_epoch_count}/{SPRAY_EPOCHS})"
            )

            stop_all()
            pump_on()

            # Sweep the hose across its full LEFT<->RIGHT
            # range instead of pinning it on the fire, so the
            # spray covers a wider area. Bounces back once it
            # hits either end.
            new_hose = current_hose + (HOSE_SWEEP_STEP * hose_sweep_direction)

            if new_hose >= HOSE_SWEEP_MAX:
                new_hose = HOSE_SWEEP_MAX
                hose_sweep_direction = -1
            elif new_hose <= HOSE_SWEEP_MIN:
                new_hose = HOSE_SWEEP_MIN
                hose_sweep_direction = 1

            move_hose(new_hose)

            cv2.putText(
                display, f"SPRAYING {spray_epoch_count}/{SPRAY_EPOCHS}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )

            if spray_epoch_count >= SPRAY_EPOCHS:

                print(f"{SPRAY_EPOCHS} spray epochs done — checking if fire is still there...")

                check_frame = picam2.capture_array()
                check_display, check_detections = detect(check_frame)

                if check_detections:
                    print("Fire still detected — continuing spray.")
                    spray_epoch_count = 0

                else:
                    print("Fire no longer detected — treating as extinguished, stopping spray.")
                    pump_off()
                    stop_all()

                    cv2.imshow("Fire Detection", check_display)
                    cv2.waitKey(1)

                    return

        elif box_close_enough:

            # ALIGNING: distance is right (box is wide enough) but
            # the body isn't squared up at the confirmed spray
            # angle yet. Stop driving forward — take small steering
            # nudges to actively walk current_pan toward
            # PAN_SPRAY_TARGET instead. The camera-centering logic
            # in step 1 above keeps re-centering the fire on screen
            # after each nudge, same as it does during approach.

            pump_off()
            spray_epoch_count = 0
            is_spraying = False

            if current_hose != HOSE_FORWARD:
                move_hose(HOSE_FORWARD)
                hose_sweep_direction = 1

            if not pan_aligned:

                if pan_error_from_target > 0:
                    print(f"Aligning: nudging LEFT (pan={current_pan:.2f} -> target {PAN_SPRAY_TARGET})")
                    drive_pulse("left", ALIGN_STEER_PULSE_TIME_LEFT)
                else:
                    print(f"Aligning: nudging RIGHT (pan={current_pan:.2f} -> target {PAN_SPRAY_TARGET})")
                    drive_pulse("right", ALIGN_STEER_PULSE_TIME)

            else:
                # Pan is aligned; tilt isn't independently drivable
                # by the chassis, so just wait for the camera-
                # centering logic to settle it near TILT_SPRAY_TARGET.
                print(f"Pan aligned ({current_pan:.2f}); waiting on tilt ({current_tilt:.2f} -> {TILT_SPRAY_TARGET})")

            cv2.putText(
                display,
                f"ALIGNING pan={current_pan:.2f} tilt={current_tilt:.2f}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2
            )

        else:

            # APPROACH: still too far away (box not wide enough
            # yet). Steer toward the body's forward heading if
            # drifted too far, otherwise creep forward.

            pump_off()
            spray_epoch_count = 0
            is_spraying = False

            if current_hose != HOSE_FORWARD:
                move_hose(HOSE_FORWARD)
                hose_sweep_direction = 1

            pan_error = current_pan - PAN_FORWARD

            if abs(pan_error) > STEER_TOLERANCE:

                # Fire is off to a side relative to the chassis:
                # turn the body instead of just chasing with the
                # neck. Turning toward more positive pan (fire
                # was left of "forward" servo-wise) -> turn_right
                # steers the body to reduce that error; adjust
                # if your chassis turns opposite to what you see.
                if pan_error > 0:
                    print("Steering LEFT to align body with fire")
                    drive_pulse("left", STEER_PULSE_TIME_LEFT)
                else:
                    print("Steering RIGHT to align body with fire")
                    drive_pulse("right", STEER_PULSE_TIME)

            else:
                print("Body roughly aimed at fire -> creeping FORWARD (vision only, no obstacle sensor)")
                drive_pulse("forward", FORWARD_PULSE_TIME)

            cv2.putText(
                display, f"APPROACHING box={fire_box_width}px", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2
            )

        # Yellow box = the neck's centering deadzone (CENTER_TOLERANCE_X/Y).
        # As long as the green dot stays inside it, pan/tilt won't move.
        # This is now ALSO the box used for the spray-trigger's
        # "fire centered on screen" check above.
        cv2.rectangle(
            display,
            (CENTER_X - CENTER_TOLERANCE_X, CENTER_Y - CENTER_TOLERANCE_Y),
            (CENTER_X + CENTER_TOLERANCE_X, CENTER_Y + CENTER_TOLERANCE_Y),
            (255, 200, 0), 2
        )
        cv2.circle(display, (CENTER_X, CENTER_Y), 7, (255, 255, 255), -1)
        cv2.circle(display, (fire_center_x, fire_center_y), 7, (0, 255, 0), -1)
        cv2.line(display, (CENTER_X, CENTER_Y), (fire_center_x, fire_center_y), (0, 255, 0), 2)

        cv2.imshow("Fire Detection", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            raise KeyboardInterrupt

        time.sleep(TRACK_DELAY)


# ============================================================
# MAIN
# ============================================================

try:

    print()
    print("========================================")
    print("      FIREBOT — AUTONOMOUS SEEK & HOLD")
    print("========================================")
    print(f"Spray trigger: box>={FIRE_CLOSE_BOX_WIDTH_PX}px, then ALIGN body until "
          f"pan~{PAN_SPRAY_TARGET}(+/-{PAN_SPRAY_TOLERANCE}) and tilt~{TILT_SPRAY_TARGET}"
          f"(+/-{TILT_SPRAY_TOLERANCE}), held for {SPRAY_TRIGGER_CONFIRM_FRAMES} frames")
    print(f"PAN_FORWARD (calibrate this!): {PAN_FORWARD}")
    print("========================================")

    while True:

        try:
            found = search_for_fire()

            if found:
                track_and_approach()
            else:
                print("Full sweep complete, no fire found. Sweeping again...")

        except KeyboardInterrupt:
            raise

        except Exception as e:
            # A camera hiccup, a bad detection frame, or any other
            # one-off error used to kill the whole run since only
            # KeyboardInterrupt was caught. Now the robot logs it,
            # stops motors/pump for safety, and goes back to
            # searching instead of dying mid-competition.
            print(f"[main loop] unexpected error, recovering: {e}")
            stop_all()
            pump_off()
            time.sleep(0.5)


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

    print("Motors stopped. GPIO cleaned up.")
    print("Pan/tilt/hose servos released.")
    print("Camera stopped.")
    print("FireBot stopped.")
