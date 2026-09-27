
import cv2
import time

from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
from picamera2 import Picamera2

from detect import detect


# ============================================================
# SERVO SETUP
# ============================================================

factory = PiGPIOFactory()


# ============================================================
# PAN SERVO
# GPIO 12 / Physical Pin 32
# ============================================================

pan_servo = Servo(
    12,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)


# ============================================================
# TILT SERVO
# GPIO 13 / Physical Pin 33
# ============================================================

tilt_servo = Servo(
    13,
    min_pulse_width=0.5 / 1000,
    max_pulse_width=2.5 / 1000,
    pin_factory=factory
)


# ============================================================
# CAMERA
# ============================================================

print("Starting camera...")

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

picam2.configure(config)
picam2.start()

time.sleep(2)

print("Camera started.")


# ============================================================
# IMAGE CENTER
# ============================================================

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

CENTER_X = FRAME_WIDTH // 2
CENTER_Y = FRAME_HEIGHT // 2


# ============================================================
# SCANNING SETTINGS
# ============================================================

SCAN_TIME = 5.0

SERVO_SETTLE_TIME = 0.30


# ============================================================
# TRACKING SETTINGS
# ============================================================

PAN_STEP = 0.02
TILT_STEP = 0.02

CENTER_TOLERANCE_X = 40
CENTER_TOLERANCE_Y = 40

TRACK_DELAY = 0.08


# ============================================================
# FIRE LOSS
# ============================================================

NO_FIRE_LIMIT = 15


# ============================================================
# PAN RANGE
# ============================================================

PAN_MIN = -0.50
PAN_MAX = 1.00


# ============================================================
# TILT LOGICAL RANGE
# ============================================================

TILT_LOGICAL_MIN = -0.20
TILT_LOGICAL_MAX = 0.70


# ============================================================
# TILT MAPPING
# ============================================================

def tilt_to_servo(logical_value):

    if logical_value < TILT_LOGICAL_MIN:
        logical_value = TILT_LOGICAL_MIN

    if logical_value > TILT_LOGICAL_MAX:
        logical_value = TILT_LOGICAL_MAX

    normalized = (
        (logical_value - TILT_LOGICAL_MIN)
        /
        (TILT_LOGICAL_MAX - TILT_LOGICAL_MIN)
    )

    servo_value = -1.0 + (normalized * 2.0)

    return servo_value


# ============================================================
# CURRENT POSITION
# ============================================================

current_pan = 1.00
current_tilt = 0.40


# ============================================================
# MOVE PAN
# ============================================================

def move_pan(value):

    global current_pan

    value = max(
        PAN_MIN,
        min(PAN_MAX, value)
    )

    print()
    print(
        f"PAN MOVING: "
        f"{current_pan:.2f} -> {value:.2f}"
    )

    pan_servo.value = value

    time.sleep(SERVO_SETTLE_TIME)

    current_pan = value

    print(
        f"PAN STOPPED: "
        f"{current_pan:.2f}"
    )


# ============================================================
# MOVE TILT
# ============================================================

def move_tilt(logical_value):

    global current_tilt

    logical_value = max(
        TILT_LOGICAL_MIN,
        min(
            TILT_LOGICAL_MAX,
            logical_value
        )
    )

    servo_value = tilt_to_servo(
        logical_value
    )

    print()
    print(
        f"TILT MOVING: "
        f"{current_tilt:.2f} -> {logical_value:.2f}"
    )

    print(
        f"Tilt servo value: "
        f"{servo_value:.3f}"
    )

    tilt_servo.value = servo_value

    time.sleep(SERVO_SETTLE_TIME)

    current_tilt = logical_value

    print(
        f"TILT STOPPED: "
        f"{current_tilt:.2f}"
    )


# ============================================================
# FIRE TRACKING
# ============================================================

def tracking_mode():

    global current_pan
    global current_tilt

    print()
    print("========================================")
    print("        FIRE TRACKING MODE")
    print("========================================")
    print("HORIZONTAL FIRST")
    print("PAN -> CENTER -> TILT -> CENTER")
    print(
        f"Fire loss limit: "
        f"{NO_FIRE_LIMIT} frames"
    )
    print("========================================")
    print()

    no_fire_count = 0

    while True:

        # ====================================================
        # CAPTURE FRAME
        # ====================================================

        frame = picam2.capture_array()

        display, detections = detect(frame)


        # ====================================================
        # NO FIRE
        # ====================================================

        if not detections:

            no_fire_count += 1

            print(
                f"No fire: "
                f"{no_fire_count}/{NO_FIRE_LIMIT}"
            )

            cv2.putText(
                display,
                f"NO FIRE "
                f"{no_fire_count}/{NO_FIRE_LIMIT}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )

            if no_fire_count >= NO_FIRE_LIMIT:

                print()
                print(
                    "Fire lost for 16 consecutive frames."
                )

                print(
                    "Returning to scanning..."
                )

                return


        # ====================================================
        # FIRE FOUND
        # ====================================================

        else:

            no_fire_count = 0

            target = max(
                detections,
                key=lambda d: d["confidence"]
            )

            x1, y1, x2, y2 = target["box"]


            # =================================================
            # FIRE CENTER
            # =================================================

            fire_center_x = int(
                (x1 + x2) / 2
            )

            fire_center_y = int(
                (y1 + y2) / 2
            )


            # =================================================
            # ERROR
            # =================================================

            error_x = (
                fire_center_x
                -
                CENTER_X
            )

            error_y = (
                fire_center_y
                -
                CENTER_Y
            )


            # =================================================
            # PRINT CENTER INFORMATION
            # =================================================

            print()
            print("----------------------------------------")

            print(
                f"Fire center: "
                f"({fire_center_x}, {fire_center_y})"
            )

            print(
                f"Camera center: "
                f"({CENTER_X}, {CENTER_Y})"
            )

            print(
                f"Horizontal error: "
                f"{error_x}"
            )

            print(
                f"Vertical error: "
                f"{error_y}"
            )

            print(
                f"Confidence: "
                f"{target['confidence']:.2f}"
            )


            # =================================================
            # DRAW CAMERA CENTER
            # =================================================

            cv2.circle(
                display,
                (
                    CENTER_X,
                    CENTER_Y
                ),
                7,
                (255, 255, 255),
                -1
            )


            # =================================================
            # DRAW FIRE CENTER
            # =================================================

            cv2.circle(
                display,
                (
                    fire_center_x,
                    fire_center_y
                ),
                7,
                (0, 255, 0),
                -1
            )


            # =================================================
            # DRAW LINE BETWEEN CENTERS
            # =================================================

            cv2.line(
                display,
                (
                    CENTER_X,
                    CENTER_Y
                ),
                (
                    fire_center_x,
                    fire_center_y
                ),
                (0, 255, 0),
                2
            )


            # =================================================
            # FIRE CENTER LABEL
            # =================================================

            cv2.putText(
                display,
                f"Fire: "
                f"({fire_center_x},{fire_center_y})",
                (
                    fire_center_x + 10,
                    fire_center_y - 10
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )


            # =================================================
            # STEP 1
            # HORIZONTAL CENTERING
            #
            # PAN HAS PRIORITY
            # TILT IS LOCKED
            # =================================================

            if abs(error_x) > CENTER_TOLERANCE_X:

                print()
                print(
                    "PAN NOT CENTERED"
                )

                print(
                    "TILT LOCKED"
                )


                # ---------------------------------------------
                # FIRE RIGHT
                # ---------------------------------------------

                if error_x > CENTER_TOLERANCE_X:

                    print(
                        "Fire RIGHT -> PAN LEFT"
                    )

                    new_pan = (
                        current_pan
                        -
                        PAN_STEP
                    )


                # ---------------------------------------------
                # FIRE LEFT
                # ---------------------------------------------

                else:

                    print(
                        "Fire LEFT -> PAN RIGHT"
                    )

                    new_pan = (
                        current_pan
                        +
                        PAN_STEP
                    )


                # ---------------------------------------------
                # PAN LIMIT
                # ---------------------------------------------

                new_pan = max(
                    PAN_MIN,
                    min(
                        PAN_MAX,
                        new_pan
                    )
                )


                print(
                    f"New PAN: "
                    f"{new_pan:.3f}"
                )


                move_pan(
                    new_pan
                )


            # =================================================
            # STEP 2
            # HORIZONTAL CENTERED
            #
            # PAN LOCKED
            # TILT CAN MOVE
            # =================================================

            else:

                print()
                print(
                    "✓ HORIZONTAL CENTERED"
                )

                print(
                    "PAN LOCKED"
                )


                # =================================================
                # VERTICAL CENTERING
                # =================================================

                if abs(error_y) > CENTER_TOLERANCE_Y:

                    print(
                        "Vertical correction required."
                    )

                    print(
                        "TILT ACTIVE"
                    )


                    # ---------------------------------------------
                    # TILT DIRECTION IS REVERSED
                    # ---------------------------------------------

                    # FIRE BELOW
                    #
                    # error_y positive
                    #
                    # Increase logical tilt

                    if error_y > CENTER_TOLERANCE_Y:

                        print(
                            "Fire BELOW -> TILT UP"
                        )

                        new_tilt = (
                            current_tilt
                            +
                            TILT_STEP
                        )


                    # ---------------------------------------------
                    # FIRE ABOVE
                    # ---------------------------------------------

                    else:

                        print(
                            "Fire ABOVE -> TILT DOWN"
                        )

                        new_tilt = (
                            current_tilt
                            -
                            TILT_STEP
                        )


                    # ---------------------------------------------
                    # TILT LIMIT
                    # ---------------------------------------------

                    new_tilt = max(
                        TILT_LOGICAL_MIN,
                        min(
                            TILT_LOGICAL_MAX,
                            new_tilt
                        )
                    )


                    print(
                        f"New TILT: "
                        f"{new_tilt:.3f}"
                    )


                    move_tilt(
                        new_tilt
                    )


                # =================================================
                # STEP 3
                # BOTH CENTERED
                # =================================================

                else:

                    print()
                    print("========================================")
                    print("🔥🔥🔥 FIRE IS CENTERED! 🔥🔥🔥")
                    print("========================================")

                    print(
                        f"Fire center: "
                        f"({fire_center_x}, {fire_center_y})"
                    )

                    print(
                        f"Camera center: "
                        f"({CENTER_X}, {CENTER_Y})"
                    )

                    print(
                        f"PAN  = "
                        f"{current_pan:.3f}"
                    )

                    print(
                        f"TILT = "
                        f"{current_tilt:.3f}"
                    )

                    print(
                        "PAN LOCKED"
                    )

                    print(
                        "TILT LOCKED"
                    )

                    cv2.putText(
                        display,
                        "FIRE CENTERED",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )


        # ====================================================
        # SHOW CAMERA
        # ====================================================

        cv2.imshow(
            "Fire Detection",
            display
        )


        # ====================================================
        # Q TO STOP
        # ====================================================

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == ord("Q"):

            raise KeyboardInterrupt


        time.sleep(TRACK_DELAY)


# ============================================================
# SCAN ONE POSITION
# ============================================================

def scan_position(
    position_name,
    pan_value,
    tilt_value
):

    global current_pan
    global current_tilt

    print()
    print("========================================")

    print(
        f"SCAN POSITION: "
        f"{position_name}"
    )

    print(
        f"PAN : "
        f"{pan_value:.2f}"
    )

    print(
        f"TILT: "
        f"{tilt_value:.2f}"
    )

    print("========================================")


    # ========================================================
    # PAN MOVES FIRST
    # ========================================================

    if pan_value != current_pan:

        move_pan(
            pan_value
        )


    # ========================================================
    # TILT MOVES AFTER PAN STOPS
    # ========================================================

    if tilt_value != current_tilt:

        move_tilt(
            tilt_value
        )


    # ========================================================
    # DETECTION WINDOW
    # ========================================================

    print()
    print(
        f"Detecting fire at "
        f"{position_name} "
        f"for {SCAN_TIME} seconds..."
    )

    start_time = time.time()


    while (
        time.time() - start_time
        <
        SCAN_TIME
    ):

        frame = picam2.capture_array()

        display, detections = detect(
            frame
        )


        # ====================================================
        # FIRE FOUND
        # ====================================================

        if detections:

            print()
            print("========================================")
            print("🔥🔥🔥 FIRE DETECTED! 🔥🔥🔥")
            print("========================================")

            print(
                f"Scan position: "
                f"{position_name}"
            )

            print(
                f"PAN : "
                f"{current_pan:.2f}"
            )

            print(
                f"TILT: "
                f"{current_tilt:.2f}"
            )


            for detection in detections:

                print(
                    f"Name       : "
                    f"{detection['class']}"
                )

                print(
                    f"Confidence : "
                    f"{detection['confidence']:.2f}"
                )

                print(
                    f"Box        : "
                    f"{detection['box']}"
                )


            print()
            print(
                "Stopping scan..."
            )

            print(
                "Starting fire tracking..."
            )


            # =================================================
            # TRACK FIRE
            # =================================================

            tracking_mode()


            # =================================================
            # FIRE LOST
            # =================================================

            print()
            print(
                "Tracking finished."
            )

            print(
                "Resuming scanning..."
            )

            return


        # ====================================================
        # DISPLAY
        # ====================================================

        cv2.imshow(
            "Fire Detection",
            display
        )


        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == ord("Q"):

            raise KeyboardInterrupt


# ============================================================
# MAIN SCANNER
#
# 8 TOTAL POSITIONS
#
# TILT = 0.40
#
#   1.00
#   0.50
#   0.00
#  -0.50
#
# TILT = 0.60
#
#  -0.50
#   0.00
#   0.50
#   1.00
#
# PAN MINIMUM = -0.50
# ============================================================

try:

    epoch = 0

    while True:

        epoch += 1

        print()
        print()
        print("========================================")
        print(
            f"              EPOCH {epoch}"
        )
        print("========================================")

        print()
        print(
            "8-POSITION FIRE SCAN"
        )

        print()

        print(
            "TILT 0.40:"
        )

        print(
            "1.00 -> "
            "0.50 -> "
            "0.00 -> "
            "-0.50"
        )

        print()

        print(
            "TILT 0.60:"
        )

        print(
            "-0.50 -> "
            "0.00 -> "
            "0.50 -> "
            "1.00"
        )

        print()

        print(
            "TOTAL POSITIONS: 8"
        )


        # ====================================================
        # TILT = 0.40
        # PAN RIGHT -> LEFT
        # ====================================================

        print()
        print(
            "******** TILT = 0.40 ********"
        )


        scan_position(
            "1/8",
            1.00,
            0.40
        )


        scan_position(
            "2/8",
            0.50,
            0.40
        )


        scan_position(
            "3/8",
            0.00,
            0.40
        )


        scan_position(
            "4/8",
            -0.50,
            0.40
        )


        # ====================================================
        # CHANGE TILT
        #
        # PAN STAYS AT -0.50
        # ONLY TILT MOVES
        # ====================================================

        print()
        print(
            "******** CHANGING TILT 0.40 -> 0.60 ********"
        )

        move_tilt(
            0.60
        )


        # ====================================================
        # TILT = 0.60
        # PAN LEFT -> RIGHT
        # ====================================================

        print()
        print(
            "******** TILT = 0.60 ********"
        )


        scan_position(
            "5/8",
            -0.50,
            0.60
        )


        scan_position(
            "6/8",
            0.00,
            0.60
        )


        scan_position(
            "7/8",
            0.50,
            0.60
        )


        scan_position(
            "8/8",
            1.00,
            0.60
        )


        # ====================================================
        # EPOCH COMPLETE
        # ====================================================

        print()
        print("========================================")

        print(
            f"EPOCH {epoch} COMPLETE"
        )

        print(
            "8 POSITIONS COMPLETE"
        )

        print("========================================")


# ============================================================
# CLEAN SHUTDOWN
# ============================================================

except KeyboardInterrupt:

    print()
    print(
        "Stopping FireBot..."
    )


finally:

    pan_servo.value = None
    tilt_servo.value = None

    picam2.stop()

    cv2.destroyAllWindows()

    print(
        "Camera stopped."
    )

    print(
        "Pan servo released."
    )

    print(
        "Tilt servo released."
    )

    print(
        "FireBot stopped."
    )

