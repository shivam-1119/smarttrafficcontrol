"""
Phase 2: YOLO Vehicle Detection Engine
Performs real-time object detection for vehicles, bicycles, pedestrians and traffic objects.
Extracts bounding boxes, exact coordinates, confidences, and vehicle classes.
"""
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from ultralytics import YOLO
import os

# Class Colors (BGR)
CLASS_COLORS = {
    "car": (240, 140, 0),        # Cyan-Blue
    "motorcycle": (200, 50, 240), # Purple-Pink
    "bus": (0, 165, 255),        # Orange
    "truck": (50, 200, 50),      # Bright Green
    "bicycle": (220, 220, 0),    # Yellow
    "person": (180, 180, 180),   # Light Grey
    "traffic light": (0, 0, 255),# Red
    "default": (100, 200, 255)
}

TARGET_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    9: "traffic light"
}


class VehicleDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.35, iou_threshold: float = 0.45):
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # Load YOLO model
        model_path = os.path.join(os.path.dirname(__file__), model_name)
        if not os.path.exists(model_path):
            model_path = model_name # Ultralytics will auto-download if needed
            
        print(f"[Detector] Loading YOLO model: {model_path}...")
        self.model = YOLO(model_path)
        print("[Detector] Model loaded successfully.")

    def set_confidence(self, conf: float):
        self.conf_threshold = max(0.1, min(0.95, conf))

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs YOLO inference on a frame.
        Returns a structured list of detected objects with spatial location & metrics.
        """
        if frame is None or frame.size == 0:
            return []

        # Run inference (verbose=False for speed)
        results = self.model.predict(
            source=frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=list(TARGET_CLASSES.keys()),
            verbose=False
        )

        detections = []
        if not results or len(results) == 0:
            return detections

        r = results[0]
        boxes = r.boxes

        if boxes is None or len(boxes) == 0:
            return detections

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            x1, y1, x2, y2 = xyxy

            cls_name = TARGET_CLASSES.get(cls_id, self.model.names.get(cls_id, "unknown"))
            color = CLASS_COLORS.get(cls_name, CLASS_COLORS["default"])

            w = x2 - x1
            h = y2 - y1
            cx = int(x1 + w / 2)
            cy = int(y1 + h / 2)

            detections.append({
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": round(conf, 3),
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "xywh": [int(x1), int(y1), int(w), int(h)],
                "centroid": (cx, cy),
                "width": int(w),
                "height": int(h),
                "area": int(w * h),
                "color": color
            })

        return detections
