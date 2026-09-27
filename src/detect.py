import cv2
import ncnn
import numpy as np


MODEL_DIR = "../models/best_ncnn_model"

INPUT_SIZE = 640

FIRE_CONF = 0.40
NMS_THRESHOLD = 0.45

CLASS_NAMES = ["fire"]

DEBUG = True


# ============================================================
# LOAD NCNN MODEL
# ============================================================

print("Loading NCNN model...")

net = ncnn.Net()

net.load_param(
    MODEL_DIR + "/model.ncnn.param"
)

net.load_model(
    MODEL_DIR + "/model.ncnn.bin"
)

print("NCNN model loaded successfully.")


# ============================================================
# NMS
# ============================================================

def nms(boxes, scores, threshold):

    if len(boxes) == 0:
        return []

    boxes = np.asarray(
        boxes,
        dtype=np.float32
    )

    scores = np.asarray(
        scores,
        dtype=np.float32
    )

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (
        np.maximum(0, x2 - x1)
        *
        np.maximum(0, y2 - y1)
    )

    order = scores.argsort()[::-1]

    keep = []

    while len(order) > 0:

        i = order[0]

        keep.append(i)

        if len(order) == 1:
            break

        xx1 = np.maximum(
            x1[i],
            x1[order[1:]]
        )

        yy1 = np.maximum(
            y1[i],
            y1[order[1:]]
        )

        xx2 = np.minimum(
            x2[i],
            x2[order[1:]]
        )

        yy2 = np.minimum(
            y2[i],
            y2[order[1:]]
        )

        w = np.maximum(
            0,
            xx2 - xx1
        )

        h = np.maximum(
            0,
            yy2 - yy1
        )

        intersection = w * h

        union = (
            areas[i]
            +
            areas[order[1:]]
            -
            intersection
        )

        iou = np.zeros_like(
            intersection
        )

        valid = union > 0

        iou[valid] = (
            intersection[valid]
            /
            union[valid]
        )

        order = order[1:][
            iou <= threshold
        ]

    return keep


# ============================================================
# FIRE DETECTOR
# ============================================================

def detect(frame):

    original_h, original_w = frame.shape[:2]

    # Same flip as your original detector
    frame = cv2.flip(frame, -1)

    # Resize
    img = cv2.resize(
        frame,
        (INPUT_SIZE, INPUT_SIZE),
        interpolation=cv2.INTER_LINEAR
    )

    # BGR -> RGB
    img = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2RGB
    )

    # Normalize
    img = img.astype(
        np.float32
    ) / 255.0

    # Debug input
    if DEBUG and not getattr(
        detect,
        "_dumped",
        False
    ):

        debug_img = (
            img * 255
        ).astype(np.uint8)

        cv2.imwrite(
            "debug_model_input.jpg",
            cv2.cvtColor(
                debug_img,
                cv2.COLOR_RGB2BGR
            )
        )

        detect._dumped = True

        print(
            "Saved debug_model_input.jpg"
        )

    # HWC -> CHW
    img = np.transpose(
        img,
        (2, 0, 1)
    )

    img = np.ascontiguousarray(
        img,
        dtype=np.float32
    )

    mat = ncnn.Mat(img)


    # ========================================================
    # NCNN INFERENCE
    # ========================================================

    with net.create_extractor() as ex:

        ret = ex.input(
            "in0",
            mat
        )

        if ret != 0:

            print(
                "NCNN input error:",
                ret
            )

            return frame, []

        ret, output = ex.extract(
            "out0"
        )

        if ret != 0:

            print(
                "NCNN extraction error:",
                ret
            )

            return frame, []


    arr = np.array(
        output,
        dtype=np.float32
    )


    # ========================================================
    # CHECK OUTPUT
    # ========================================================

    if arr.shape != (6, 8400):

        print(
            "Unexpected output shape:",
            arr.shape
        )

        return frame, []


    arr = np.nan_to_num(
        arr,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )


    if DEBUG:

        print(
            f"max fire_score="
            f"{arr[4].max():.3f}"
        )


    # ========================================================
    # DETECTIONS
    # ========================================================

    boxes = []
    scores = []
    classes = []


    for i in range(8400):

        cx = float(
            arr[0, i]
        )

        cy = float(
            arr[1, i]
        )

        w = float(
            arr[2, i]
        )

        h = float(
            arr[3, i]
        )


        if not np.isfinite(
            cx + cy + w + h
        ):

            continue


        x1 = cx - w / 2.0
        y1 = cy - h / 2.0

        x2 = cx + w / 2.0
        y2 = cy + h / 2.0


        if x2 < x1:

            x1, x2 = x2, x1


        if y2 < y1:

            y1, y2 = y2, y1


        x1c = max(
            0.0,
            min(x1, 639.0)
        )

        y1c = max(
            0.0,
            min(y1, 639.0)
        )

        x2c = max(
            0.0,
            min(x2, 639.0)
        )

        y2c = max(
            0.0,
            min(y2, 639.0)
        )


        if (
            x2c <= x1c
            or
            y2c <= y1c
        ):

            continue


        if (
            (x2c - x1c) < 3
            or
            (y2c - y1c) < 3
        ):

            continue


        fire_score = float(
            arr[4, i]
        )


        if not np.isfinite(
            fire_score
        ):

            continue


        if fire_score < FIRE_CONF:

            continue


        boxes.append([
            x1c,
            y1c,
            x2c,
            y2c
        ])

        scores.append(
            fire_score
        )

        classes.append(0)


    # ========================================================
    # NMS
    # ========================================================

    final_indices = nms(
        boxes,
        scores,
        NMS_THRESHOLD
    )

    detections = []


    # ========================================================
    # DRAW RESULTS
    # ========================================================

    scale_x = (
        original_w
        /
        INPUT_SIZE
    )

    scale_y = (
        original_h
        /
        INPUT_SIZE
    )

    BOX_COLOR = {
        0: (0, 0, 255)
    }


    for i in final_indices:

        x1, y1, x2, y2 = boxes[i]

        x1 = int(
            x1 * scale_x
        )

        y1 = int(
            y1 * scale_y
        )

        x2 = int(
            x2 * scale_x
        )

        y2 = int(
            y2 * scale_y
        )


        score = scores[i]

        class_id = classes[i]

        label = CLASS_NAMES[
            class_id
        ]

        color = BOX_COLOR[
            class_id
        ]


        # Bounding box
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            color,
            2
        )


        # Name + confidence
        cv2.putText(
            frame,
            f"{label} {score:.2f}",
            (
                x1,
                max(
                    20,
                    y1 - 8
                )
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )


        detections.append({
            "class": label,
            "confidence": score,
            "box": (
                x1,
                y1,
                x2,
                y2
            )
        })


    return frame, detections
