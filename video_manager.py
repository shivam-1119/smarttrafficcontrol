"""
Phase 1: Video Ingestion & Camera Input Management Module
Handles real-time webcam streams, sample traffic videos, uploaded files, and RTSP streams.
"""
import os
import cv2
import time
import threading
import glob
from typing import Dict, List, Optional, Tuple, Any

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class VideoSourceManager:
    def __init__(self):
        self.current_source_type: str = "sample"
        self.current_source_val: str = "urban_intersection.mp4"
        self.cap: Optional[cv2.VideoCapture] = None
        self.running: bool = False
        self.lock = threading.Lock()
        self.current_frame: Optional[any] = None
        self.frame_width: int = 1280
        self.frame_height: int = 720
        self.fps: float = 30.0
        self.frame_count: int = 0
        self.is_paused: bool = False
        self.loop_video: bool = True
        self.worker_thread: Optional[threading.Thread] = None
        
        # Start initial default source
        default_video = os.path.join(SAMPLE_DIR, "urban_intersection.mp4")
        if not os.path.exists(default_video):
            default_video = os.path.join(SAMPLE_DIR, "highway_traffic.mp4")
        
        self.set_source("sample", os.path.basename(default_video))

    def detect_available_cameras(self, max_test: int = 4) -> List[Dict[str, Any]]:
        """Scans for accessible physical/virtual webcam devices."""
        available = []
        for index in range(max_test):
            # On Windows, cv2.CAP_DSHOW or default CAP_ANY
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    available.append({
                        "id": f"camera:{index}",
                        "name": f"Live Camera / Webcam {index} ({w}x{h})",
                        "type": "camera",
                        "value": str(index),
                        "resolution": f"{w}x{h}",
                        "fps": round(fps, 1)
                    })
                cap.release()
        return available

    def list_sample_videos(self) -> List[Dict[str, Any]]:
        """Returns all prepared sample traffic videos."""
        samples = []
        pattern = os.path.join(SAMPLE_DIR, "*.mp4")
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            title = filename.replace(".mp4", "").replace("_", " ").title()
            samples.append({
                "id": f"sample:{filename}",
                "name": f"Sample: {title} ({size_mb} MB)",
                "type": "sample",
                "value": filename,
                "path": filepath
            })
        return samples

    def list_uploaded_videos(self) -> List[Dict[str, Any]]:
        """Returns user uploaded videos."""
        uploads = []
        for ext in ("*.mp4", "*.avi", "*.mov", "*.mkv"):
            for filepath in glob.glob(os.path.join(UPLOAD_DIR, ext)):
                filename = os.path.basename(filepath)
                size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
                uploads.append({
                    "id": f"upload:{filename}",
                    "name": f"Upload: {filename} ({size_mb} MB)",
                    "type": "upload",
                    "value": filename,
                    "path": filepath
                })
        return uploads

    def get_all_sources(self) -> Dict[str, Any]:
        """Returns catalog of all available video sources."""
        return {
            "current_source": {
                "type": self.current_source_type,
                "value": self.current_source_val,
                "resolution": f"{self.frame_width}x{self.frame_height}",
                "fps": round(self.fps, 1)
            },
            "cameras": self.detect_available_cameras(),
            "samples": self.list_sample_videos(),
            "uploads": self.list_uploaded_videos()
        }

    def set_source(self, source_type: str, source_val: str) -> bool:
        """
        Switch video source smoothly.
        source_type: 'camera', 'sample', 'upload', 'stream'
        source_val: '0', 'urban_intersection.mp4', 'rtsp://...', etc.
        """
        with self.lock:
            self.running = False
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            resolved_path = None
            if source_type == "camera":
                try:
                    cam_idx = int(source_val)
                    self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(cam_idx)
                except ValueError:
                    return False

            elif source_type == "sample":
                resolved_path = os.path.join(SAMPLE_DIR, source_val)
                if not os.path.exists(resolved_path):
                    return False
                self.cap = cv2.VideoCapture(resolved_path)

            elif source_type == "upload":
                resolved_path = os.path.join(UPLOAD_DIR, source_val)
                if not os.path.exists(resolved_path):
                    return False
                self.cap = cv2.VideoCapture(resolved_path)

            elif source_type == "stream":
                self.cap = cv2.VideoCapture(source_val)

            else:
                return False

            if not self.cap or not self.cap.isOpened():
                print(f"[VideoManager] Error opening source: {source_type}:{source_val}")
                return False

            self.current_source_type = source_type
            self.current_source_val = source_val
            
            # Read first frame to initialize resolution
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.frame_height, self.frame_width = frame.shape[:2]
                self.current_frame = frame.copy()
            
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if self.fps <= 0 or self.fps > 120:
                self.fps = 30.0
                
            self.running = True
            
            # Start background reader thread
            if self.worker_thread and self.worker_thread.is_alive():
                pass # thread will exit as self.running was reset
                
            self.worker_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.worker_thread.start()
            print(f"[VideoManager] Active source switched to: {source_type}:{source_val} ({self.frame_width}x{self.frame_height} @ {self.fps:.1f} FPS)")
            return True

    def _capture_loop(self):
        """Dedicated thread to continuously capture frames and handle loop/throttling."""
        frame_delay = 1.0 / self.fps if self.fps > 0 else 0.033
        
        while self.running:
            if self.is_paused:
                time.sleep(0.05)
                continue

            start_time = time.time()
            if self.cap is None or not self.cap.isOpened():
                break

            ret, frame = self.cap.read()
            if not ret or frame is None:
                # Video ended -> loop if enabled
                if self.loop_video and self.current_source_type in ["sample", "upload"]:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        time.sleep(0.1)
                        continue
                else:
                    time.sleep(0.1)
                    continue

            with self.lock:
                self.current_frame = frame
                self.frame_count += 1

            # Throttle frame rate for video files so playback speed is natural
            if self.current_source_type in ["sample", "upload"]:
                elapsed = time.time() - start_time
                wait_time = frame_delay - elapsed
                if wait_time > 0.002:
                    time.sleep(wait_time)

    def read_frame(self) -> Tuple[bool, Optional[any]]:
        """Returns the latest captured frame."""
        with self.lock:
            if self.current_frame is None:
                return False, None
            return True, self.current_frame.copy()

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def toggle_pause(self) -> bool:
        self.is_paused = not self.is_paused
        return self.is_paused

    def release(self):
        self.running = False
        if self.cap:
            self.cap.release()
