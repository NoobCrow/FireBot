import cv2
import numpy as np
import ncnn
from picamera2 import Picamera2

MODEL_DIR = "models/best_ncnn_model"
INPUT_SIZE = 640
CONF_THRESHOLD = 0.25
NMS_THRESHOLD = 0.45

# Class names from your FireBot model
CLASS_NAMES = ["fire", "smoke"]

# -----------------------------
# Load NCNN model
# -----------------------------
net = ncnn.Net()
net.load_param(f"{MODEL_DIR}/model.ncnn.param")
net.load_model(f"{MODEL_DIR}/model.ncnn.bin")

print("NCNN MODEL LOADED")

# -----------------------------
# Start Raspberry Pi camera
# -----------------------------
picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)

picam2.configure(config)
picam2.start()

print("CAMERA STARTED")
print("Press Q to quit")

# -----------------------------
# Main loop
# -----------------------------
while True:

    frame = picam2.capture_array()

    original_h, original_w = frame.shape[:2]

    # RGB -> BGR for OpenCV
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Resize to model input
    image = cv2.resize(
        frame_bgr,
        (INPUT_SIZE, INPUT_SIZE),
        interpolation=cv2.INTER_LINEAR
    )

    # BGR -> RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Convert to NCNN Mat
    mat = ncnn.Mat(
        image.astype(np.float32),
        pixel_type=ncnn.Mat.PIXEL_RGB
    )

    # Normalize 0-255 -> 0-1
    mat.substract_mean_normalize(
        np.array([], dtype=np.float32),
        np.array([1 / 255.0, 1 / 255.0, 1 / 255.0], dtype=np.float32)
    )

    # -----------------------------
    # NCNN inference
    # -----------------------------
    with net.create_extractor() as ex:

        ex.input("in0", mat)

        ret, output = ex.extract("out0")

        if ret != 0:
            print("NCNN inference error:", ret)
            continue

    output = np.array(output)

    # -----------------------------
    # YOLO output
    # -----------------------------
    # Expected output:
    # 8400 detections × 6+
    #
    # x, y, w, h, confidence, class...
    # -----------------------------

    if output.ndim == 3:
        output = output.reshape(-1, output.shape[-1])

    detections = []

    for detection in output:

        if len(detection) < 6:
            continue

        x, y, w, h = detection[:4]

        class_scores = detection[4:]

        class_id = int(np.argmax(class_scores))
        confidence = float(class_scores[class_id])

        if confidence < CONF_THRESHOLD:
            continue

        # Convert center coordinates to corners
        x1 = int((x - w / 2) * original_w / INPUT_SIZE)
        y1 = int((y - h / 2) * original_h / INPUT_SIZE)

        x2 = int((x + w / 2) * original_w / INPUT_SIZE)
        y2 = int((y + h / 2) * original_h / INPUT_SIZE)

        x1 = max(0, min(original_w - 1, x1))
        y1 = max(0, min(original_h - 1, y1))
        x2 = max(0, min(original_w - 1, x2))
        y2 = max(0, min(original_h - 1, y2))

        detections.append(
            (x1, y1, x2, y2, confidence, class_id)
        )

    # -----------------------------
    # NMS
    # -----------------------------
    boxes = []
    scores = []
    class_ids = []

    for x1, y1, x2, y2, confidence, class_id in detections:

        boxes.append([
            x1,
            y1,
            x2 - x1,
            y2 - y1
        ])

        scores.append(confidence)
        class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(
        boxes,
        scores,
        CONF_THRESHOLD,
        NMS_THRESHOLD
    )

    # -----------------------------
    # Draw detections
    # -----------------------------
    if len(indices) > 0:

        for i in np.array(indices).flatten():

            x, y, w, h = boxes[i]

            confidence = scores[i]
            class_id = class_ids[i]

            if class_id < len(CLASS_NAMES):
                label = CLASS_NAMES[class_id]
            else:
                label = f"class_{class_id}"

            # Center position
            center_x = x + w // 2
            center_y = y + h // 2

            # Draw box
            cv2.rectangle(
                frame_bgr,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            # Draw center
            cv2.circle(
                frame_bgr,
                (center_x, center_y),
                5,
                (0, 0, 255),
                -1
            )

            text = (
                f"{label} {confidence:.2f} "
                f"X:{center_x} Y:{center_y}"
            )

            cv2.putText(
                frame_bgr,
                text,
                (x, max(25, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            # Print detection
            print(
                f"{label}: "
                f"{confidence:.2f} "
                f"center=({center_x},{center_y})"
            )

    # -----------------------------
    # Display
    # -----------------------------
    cv2.imshow("FireBot NCNN Camera", frame_bgr)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


picam2.stop()
cv2.destroyAllWindows()

print("Camera stopped.")
