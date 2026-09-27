# Models
- `best.pt`: YOLOv8n fine-tuned on the [Home Fire Dataset](https://www.kaggle.com/datasets/pengbo00/home-fire-dataset) (`fire`, `smoke`); 640×640 input, 50 epochs
- `best_ncnn_model/`: NCNN export (`model.ncnn.param` / `model.ncnn.bin`), used by `src/detect.py` for CPU-only inference on the Pi 4

The robot controller acts on the **fire** output only.
