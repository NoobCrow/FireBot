import cv2
import numpy as np
import ncnn

MODEL_DIR = "models/best_ncnn_model"
IMAGE_PATH = "test.jpg"

IMG_SIZE = 640
CONF_THRESHOLD = 0.25
NMS_THRESHOLD = 0.45


def main():

    image = cv2.imread(IMAGE_PATH)

    if image is None:
        print("ERROR: Cannot read test.jpg")
        return

    original_h, original_w = image.shape[:2]

    resized = cv2.resize(image, (IMG_SIZE, IMG_SIZE))

    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    net = ncnn.Net()

    net.load_param(f"{MODEL_DIR}/model.ncnn.param")
    net.load_model(f"{MODEL_DIR}/model.ncnn.bin")

    mat = ncnn.Mat.from_pixels(
        rgb,
        ncnn.Mat.PixelType.PIXEL_RGB,
        IMG_SIZE,
        IMG_SIZE
    )

    mat.substract_mean_normalize(
        [],
        [1 / 255.0, 1 / 255.0, 1 / 255.0]
    )

    ex = net.create_extractor()

    ex.input("in0", mat)

    ret, out = ex.extract("out0")

    if ret != 0:
        print("NCNN inference failed:", ret)
        return

    predictions = np.array(out).T

    print("Predictions:", predictions.shape)

    boxes = []
    scores = []

    for prediction in predictions:

        x1, y1, x2, y2, obj_conf, class_conf = prediction

        confidence = obj_conf * class_conf

        if confidence < CONF_THRESHOLD:
            continue

        # Convert coordinates from 640x640
        scale_x = original_w / IMG_SIZE
        scale_y = original_h / IMG_SIZE

        x1 = int(x1 * scale_x)
        y1 = int(y1 * scale_y)
        x2 = int(x2 * scale_x)
        y2 = int(y2 * scale_y)

        width = x2 - x1
        height = y2 - y1

        if width <= 0 or height <= 0:
            continue

        boxes.append([x1, y1, width, height])
        scores.append(float(confidence))

    print("Candidates above threshold:", len(boxes))

    if len(boxes) == 0:
        print("NO FIRE DETECTED")
        return

    indices = cv2.dnn.NMSBoxes(
        boxes,
        scores,
        CONF_THRESHOLD,
        NMS_THRESHOLD
    )

    if len(indices) == 0:
        print("NO FIRE DETECTED")
        return

    print()
    print("🔥 FIRE DETECTED")
    print("================")

    for i in indices:

        i = int(i)

        x, y, w, h = boxes[i]

        confidence = scores[i]

        print(
            f"Fire: {confidence:.3f} "
            f"Box: ({x}, {y}) -> ({x+w}, {y+h})"
        )

        cv2.rectangle(
            image,
            (x, y),
            (x + w, y + h),
            (0, 0, 255),
            2
        )

        cv2.putText(
            image,
            f"FIRE {confidence:.2f}",
            (x, max(y - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

    output_path = "fire_detection_result.jpg"

    cv2.imwrite(output_path, image)

    print()
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
