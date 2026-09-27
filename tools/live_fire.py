import cv2
import numpy as np
import ncnn
from picamera2 import Picamera2

MODEL_DIR = "models/best_ncnn_model"

# -----------------------------
# Settings
# -----------------------------
IMG_SIZE = 640
CONF_THRESHOLD = 0.25

# -----------------------------
# Load NCNN model
# -----------------------------
net = ncnn.Net()
net.load_param(f"{MODEL_DIR}/model.ncnn.param")
net.load_model(f"{MODEL_DIR}/model.ncnn.bin")

print("NCNN model loaded")

# -----------------------------
# Start Raspberry Pi camera
# -----------------------------
picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)

picam2.configure(config)
picam2.start()

print("Camera started")
print("LIVE FIRE DETECTION")
print("Press Ctrl+C to stop")

# -----------------------------
# Detection function
# -----------------------------
def detect_fire(frame):

    h, w = frame.shape[:2]

    # Letterbox
    scale = min(IMG_SIZE / w, IMG_SIZE / h)

    nw = int(w * scale)
    nh = int(h * scale)

    resized = cv2.resize(frame, (nw, nh))

    canvas = np.full(
        (IMG_SIZE, IMG_SIZE, 3),
        114,
        dtype=np.uint8
    )

    pad_x = (IMG_SIZE - nw) // 2
    pad_y = (IMG_SIZE - nh) // 2

    canvas[
        pad_y:pad_y + nh,
        pad_x:pad_x + nw
    ] = resized

    # RGB -> NCNN
    mat = ncnn.Mat.from_pixels(
        canvas,
        ncnn.Mat.PixelType.PIXEL_RGB,
        IMG_SIZE,
        IMG_SIZE
    )

    # Normalize
    mat.substract_mean_normalize(
        [0, 0, 0],
        [1 / 255.0, 1 / 255.0, 1 / 255.0]
    )

    # Inference
    with net.create_extractor() as ex:

        ex.input("in0", mat)

        ret, out = ex.extract("out0")

        if ret != 0:
            return frame, []

        pred = np.array(out)

    # Expected output: (6, 8400)
    if pred.ndim == 2 and pred.shape[0] == 6:
        pred = pred.T

    detections = []

    for row in pred:

        x1, y1, x2, y2, confidence, class_score = row

        confidence = float(confidence)
        class_score = float(class_score)

        # Fire confidence
        score = confidence

        if score < CONF_THRESHOLD:
            continue

        # Remove padding
        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale

        # Clamp
        x1 = max(0, min(w, x1))
        y1 = max(0, min(h, y1))
        x2 = max(0, min(w, x2))
        y2 = max(0, min(h, y2))

        detections.append(
            (score, int(x1), int(y1), int(x2), int(y2))
        )

    # Keep strongest detections
    detections.sort(reverse=True)

    return frame, detections[:5]


# -----------------------------
# Main loop
# -----------------------------
try:

    while True:

        frame = picam2.capture_array()

        frame, detections = detect_fire(frame)

        # Draw detections
        for score, x1, y1, x2, y2 in detections:

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 0, 255),
                2
            )

            label = f"FIRE {score:.2f}"

            cv2.putText(
                frame,
                label,
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # Status
        if detections:

            best = detections[0][0]

            cv2.putText(
                frame,
                f"FIRE DETECTED: {best:.2f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            print(f"\rFIRE: {best:.3f}", end="", flush=True)

        else:

            cv2.putText(
                frame,
                "NO FIRE",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            print("\rNO FIRE       ", end="", flush=True)

        # Preview window
        cv2.imshow("FireBot - Live Fire Detection", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

finally:

    picam2.stop()
    cv2.destroyAllWindows()
    print("\nStopped")
