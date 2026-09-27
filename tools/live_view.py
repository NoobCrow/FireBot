import cv2
import numpy as np
import ncnn
import time
from picamera2 import Picamera2

MODEL_DIR = "models/best_ncnn_model"

CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# -----------------------------
# Load NCNN model
# -----------------------------
net = ncnn.Net()
net.load_param(f"{MODEL_DIR}/model.ncnn.param")
net.load_model(f"{MODEL_DIR}/model.ncnn.bin")

print("NCNN model loaded")

# -----------------------------
# Start camera
# -----------------------------
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

print("Camera started")
print("Live view started")
print("Press Q to quit")

# FPS
last_time = time.time()
frames = 0
fps = 0

try:

    while True:

        # Capture frame
        frame = picam2.capture_array()

        h, w = frame.shape[:2]

        # --------------------------------
        # Letterbox
        # --------------------------------

        scale = min(640 / w, 640 / h)

        nw = int(w * scale)
        nh = int(h * scale)

        resized = cv2.resize(frame, (nw, nh))

        canvas = np.full(
            (640, 640, 3),
            114,
            dtype=np.uint8
        )

        xpad = (640 - nw) // 2
        ypad = (640 - nh) // 2

        canvas[
            ypad:ypad + nh,
            xpad:xpad + nw
        ] = resized

        # --------------------------------
        # NCNN input
        # --------------------------------

        mat = ncnn.Mat.from_pixels(
            canvas,
            ncnn.Mat.PixelType.PIXEL_RGB,
            640,
            640
        )

        mat.substract_mean_normalize(
            [0, 0, 0],
            [1 / 255.0, 1 / 255.0, 1 / 255.0]
        )

        # --------------------------------
        # Inference
        # --------------------------------

        ex = net.create_extractor()

        ex.input("in0", mat)

        ret, out = ex.extract("out0")

        pred = np.array(out).T

        boxes = []
        scores = []

        # --------------------------------
        # Decode detections
        # --------------------------------

        for p in pred:

            cx, cy, bw, bh = p[:4]

            score = float(p[4])

            if score < CONF_THRESHOLD:
                continue

            x1 = (cx - bw / 2 - xpad) / scale
            y1 = (cy - bh / 2 - ypad) / scale

            x2 = (cx + bw / 2 - xpad) / scale
            y2 = (cy + bh / 2 - ypad) / scale

            x1 = max(0, min(w, x1))
            y1 = max(0, min(h, y1))

            x2 = max(0, min(w, x2))
            y2 = max(0, min(h, y2))

            boxes.append([
                x1,
                y1,
                x2 - x1,
                y2 - y1
            ])

            scores.append(score)

        # --------------------------------
        # NMS
        # --------------------------------

        if boxes:

            indices = cv2.dnn.NMSBoxes(
                boxes,
                scores,
                CONF_THRESHOLD,
                IOU_THRESHOLD
            )

        else:

            indices = []

        # --------------------------------
        # Draw fire detection
        # --------------------------------

        if len(indices) > 0:

            # Strongest detection
            best = max(
                indices,
                key=lambda i: scores[int(i)]
            )

            best = int(best)

            x, y, bw, bh = boxes[best]

            confidence = scores[best]

            x1 = int(x)
            y1 = int(y)
            x2 = int(x + bw)
            y2 = int(y + bh)

            center_x = int(x + bw / 2)
            center_y = int(y + bh / 2)

            # Direction
            if center_x < 213:
                direction = "LEFT"

            elif center_x > 426:
                direction = "RIGHT"

            else:
                direction = "CENTER"

            # Bounding box
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 0, 255),
                2
            )

            # Center point
            cv2.circle(
                frame,
                (center_x, center_y),
                6,
                (0, 255, 0),
                -1
            )

            # Text
            cv2.putText(
                frame,
                f"FIRE {confidence:.2f}",
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            cv2.putText(
                frame,
                f"Center: {center_x},{center_y}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Direction: {direction}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )

        else:

            cv2.putText(
                frame,
                "NO FIRE",
                (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

        # --------------------------------
        # FPS
        # --------------------------------

        frames += 1

        now = time.time()

        if now - last_time >= 1:

            fps = frames / (now - last_time)

            frames = 0
            last_time = now

        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        # --------------------------------
        # Show live view
        # --------------------------------

        cv2.imshow(
            "FireBot - Live Fire Detection",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

finally:

    picam2.stop()
    cv2.destroyAllWindows()

    print("Camera stopped")
    print("Program ended")
