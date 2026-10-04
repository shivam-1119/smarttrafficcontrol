"""
Master Vision & Traffic Control Pipeline
Coordinates Video Ingestion, YOLO Detection, Multi-Object Tracking,
Lane Assignment, Density Computation, and Rich HUD Visualization.
Runs an asynchronous background worker for optimal FPS and decoupled web streaming.
"""
import cv2
import time
import threading
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from collections import deque

from video_manager import VideoSourceManager
from detector import VehicleDetector, CLASS_COLORS
from tracker import VehicleTracker, TrackedVehicle
from lane_manager import LaneManager
from density_engine import TrafficDensityEngine


class TrafficPipeline:
    def __init__(self, model_name: str = "yolov8n.pt", conf_thresh: float = 0.35):
        print("[Pipeline] Initializing Smart Traffic Vision Pipeline...")
        self.video_manager = VideoSourceManager()
        self.detector = VehicleDetector(model_name=model_name, conf_threshold=conf_thresh)
        self.tracker = VehicleTracker()
        self.lane_manager = LaneManager(
            frame_width=self.video_manager.frame_width,
            frame_height=self.video_manager.frame_height
        )
        self.density_engine = TrafficDensityEngine()
        
        # Display & Overlay settings
        self.overlay_options = {
            "show_boxes": True,
            "show_labels": True,
            "show_ids": True,
            "show_speed": True,
            "show_trails": True,
            "show_lanes": True,
            "show_count_lines": True,
            "show_density_hud": True
        }
        
        # FPS and Telemetry state
        self.fps_history = deque(maxlen=20)
        self.last_frame_time = time.time()
        self.current_fps = 30.0
        
        # Recent detection log buffer (for frontend live table)
        self.recent_logs = deque(maxlen=100)
        self.latest_telemetry: Dict[str, Any] = {
            "timestamp": time.time(),
            "fps": 30.0,
            "total_active_vehicles": 0,
            "total_tracked_cumulative": 0,
            "class_distribution": {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "bicycle": 0, "person": 0},
            "overall_metrics": {
                "overall_density_category": "Low",
                "overall_density_score": 0.0,
                "overall_color": "#10b981",
                "total_active_vehicles": 0,
                "average_speed_kmh": 0.0,
                "congestion_alert": False
            },
            "lanes_density": [],
            "lanes_summary": [],
            "signals": {
                "active_green_lane": "lane_1",
                "signal_state": "GREEN",
                "remaining_seconds": 20,
                "lane_signals": {}
            },
            "active_vehicles": [],
            "recent_logs": []
        }
        
        self.latest_annotated_frame: Optional[np.ndarray] = None
        self.lock = threading.Lock()
        self.running = True
        
        # Start background pipeline worker thread
        self.worker_thread = threading.Thread(target=self._pipeline_worker, daemon=True)
        self.worker_thread.start()

    def _pipeline_worker(self):
        """Dedicated background loop that processes video frames with YOLO and tracking continuously."""
        while self.running:
            try:
                ret, frame = self.video_manager.read_frame()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue

                # 1. Update Lane Manager dimensions if frame size changed
                fh, fw = frame.shape[:2]
                if fw != self.lane_manager.frame_width or fh != self.lane_manager.frame_height:
                    self.lane_manager.frame_width = fw
                    self.lane_manager.frame_height = fh
                    self.lane_manager.load_preset(self.lane_manager.current_preset)

                # 2. YOLO Object Detection (Phase 2)
                detections = self.detector.detect(frame)

                # 3. Multi-Object Tracking & Trajectories (Phase 3)
                active_vehicles = self.tracker.update(detections)

                # 4. Multi-Lane Point-in-Polygon & Line Crossing (Phase 4)
                self.lane_manager.process_vehicles(active_vehicles)

                # 5. Density & Adaptive Traffic Signals (Phase 4)
                lane_summary = self.lane_manager.get_summary()["lanes"]
                lanes_density = []
                for l_dict in lane_summary:
                    lane_objs = [v for v in active_vehicles if v.lane_id == l_dict["lane_id"]]
                    d_info = self.density_engine.calculate_lane_density(l_dict, lane_objs)
                    lanes_density.append(d_info)

                signals_info = self.density_engine.update_signals(lanes_density)
                overall_metrics = self.density_engine.compute_overall_metrics(lanes_density, len(active_vehicles))

                # 6. FPS Calculation
                now = time.time()
                dt = now - self.last_frame_time
                self.last_frame_time = now
                if dt > 0:
                    self.fps_history.append(1.0 / dt)
                    self.current_fps = round(sum(self.fps_history) / len(self.fps_history), 1)

                # 7. Update Recent Detections Log
                for v in active_vehicles:
                    self.recent_logs.appendleft({
                        "timestamp": time.strftime("%H:%M:%S"),
                        "track_id": v.track_id,
                        "class_name": v.class_name,
                        "lane": v.lane_name or "Outside ROI",
                        "confidence": f"{int(v.confidence * 100)}%",
                        "speed_kmh": v.speed_kmh,
                        "direction": v.direction,
                        "bbox": [int(b) for b in v.bbox]
                    })

                # 8. Render Visual Overlays
                annotated_frame = self._render_overlays(
                    frame.copy(), active_vehicles, lane_summary, lanes_density, signals_info, overall_metrics
                )

                # 9. Pack Telemetry JSON Payload
                class_dist = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "bicycle": 0, "person": 0}
                for v in active_vehicles:
                    c = v.class_name.lower()
                    if c in class_dist:
                        class_dist[c] += 1
                    else:
                        class_dist["car"] += 1

                telemetry = {
                    "timestamp": time.time(),
                    "fps": self.current_fps,
                    "total_active_vehicles": len(active_vehicles),
                    "total_tracked_cumulative": self.tracker.total_tracked_cumulative,
                    "class_distribution": class_dist,
                    "overall_metrics": overall_metrics,
                    "lanes_density": lanes_density,
                    "lanes_summary": lane_summary,
                    "signals": signals_info,
                    "active_vehicles": [v.to_dict() for v in active_vehicles],
                    "recent_logs": list(self.recent_logs)[:25]
                }

                with self.lock:
                    self.latest_annotated_frame = annotated_frame
                    self.latest_telemetry = telemetry

                # Yield small slice
                time.sleep(0.01)

            except Exception as e:
                print(f"[Pipeline Worker Error] {e}")
                time.sleep(0.05)

    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Returns the most recent annotated frame in thread-safe manner."""
        with self.lock:
            if self.latest_annotated_frame is None:
                return False, None
            return True, self.latest_annotated_frame.copy()

    def get_latest_telemetry(self) -> Dict[str, Any]:
        """Returns the latest telemetry dictionary in thread-safe manner."""
        with self.lock:
            return self.latest_telemetry.copy()

    def process_next_frame(self) -> Tuple[bool, Optional[np.ndarray], Dict[str, Any]]:
        ret, frame = self.get_latest_frame()
        return ret, frame, self.get_latest_telemetry()

    def _render_overlays(self, frame: np.ndarray, vehicles: List[TrackedVehicle],
                         lanes: List[Dict[str, Any]], lanes_density: List[Dict[str, Any]],
                         signals: Dict[str, Any], overall: Dict[str, Any]) -> np.ndarray:
        """Draws aesthetic glassmorphic-inspired HUD, polygons, bounding boxes and trails."""
        h, w = frame.shape[:2]
        overlay = frame.copy()

        # 1. Draw Lane ROI Polygons & Virtual Trigger Lines
        if self.overlay_options["show_lanes"]:
            # A. Draw Semi-transparent lane fills
            for idx, l in enumerate(lanes):
                pts = np.array(l["polygon_pts"], np.int32)
                if len(pts) >= 3:
                    raw_border = l.get("border_color", [0, 200, 255])
                    fill_col = (int(raw_border[0] * 0.28), int(raw_border[1] * 0.28), int(raw_border[2] * 0.28))
                    cv2.fillPoly(overlay, [pts], fill_col)

            # Blend semi-transparent polygons with background frame first
            cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

            # B. Draw crisp borders, center badges and counting lines
            for idx, l in enumerate(lanes):
                pts = np.array(l["polygon_pts"], np.int32)
                if len(pts) >= 3:
                    raw_border = l.get("border_color", [0, 200, 255])
                    border_color = (int(raw_border[0]), int(raw_border[1]), int(raw_border[2]))
                    cv2.polylines(frame, [pts], isClosed=True, color=border_color, thickness=2)

                # Clean non-overlapping centered badge
                if len(pts) >= 2:
                    top_l = pts[0]
                    top_r = pts[1]
                    center_x = (int(top_l[0]) + int(top_r[0])) // 2
                    top_y = int(top_l[1])

                    lane_id = l["lane_id"]
                    lane_d = next((d for d in lanes_density if d["lane_id"] == lane_id), None)
                    signal_state = signals.get("lane_signals", {}).get(lane_id, {}).get("signal", "RED")
                    sig_color = (0, 255, 0) if signal_state == "GREEN" else ((0, 220, 255) if signal_state == "YELLOW" else (0, 0, 255))
                    act_cnt = l["active_count"]

                    lbl = f"L{idx+1}: {act_cnt}v"
                    tw = int(len(lbl) * 7.5) + 18
                    lx = max(4, min(w - tw - 4, center_x - tw // 2))
                    ly = max(22, top_y + 18)

                    raw_border = l.get("border_color", [0, 200, 255])
                    border_color = (int(raw_border[0]), int(raw_border[1]), int(raw_border[2]))
                    cv2.rectangle(frame, (lx, ly - 14), (lx + tw, ly + 4), (16, 22, 34), -1)
                    cv2.rectangle(frame, (lx, ly - 14), (lx + tw, ly + 4), border_color, 1)
                    cv2.circle(frame, (lx + 7, ly - 5), 4, sig_color, -1)
                    cv2.putText(frame, lbl, (lx + 15, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

                # Virtual Counting Line
                if self.overlay_options["show_count_lines"] and l.get("count_line"):
                    c_line = l["count_line"]
                    if len(c_line) == 2:
                        p1 = (int(c_line[0][0]), int(c_line[0][1]))
                        p2 = (int(c_line[1][0]), int(c_line[1][1]))
                        cv2.line(frame, p1, p2, (0, 235, 255), 2)
                        mid_x, mid_y = int((p1[0] + p2[0]) // 2), int((p1[1] + p2[1]) // 2)
                        cv2.circle(frame, (mid_x, mid_y), 4, (0, 165, 255), -1)

        # 2. Draw Motion Trails / Trajectories
        if self.overlay_options["show_trails"]:
            for v in vehicles:
                if len(v.history) > 1:
                    hist_pts = list(v.history)
                    for i in range(1, len(hist_pts)):
                        alpha = i / len(hist_pts)
                        thickness = max(1, int(3 * alpha))
                        raw_c = v.color
                        color = (int(raw_c[0]), int(raw_c[1]), int(raw_c[2]))
                        p_a = (int(hist_pts[i-1][0]), int(hist_pts[i-1][1]))
                        p_b = (int(hist_pts[i][0]), int(hist_pts[i][1]))
                        cv2.line(frame, p_a, p_b, color, thickness)

        # 3. Draw Vehicle Bounding Boxes, Labels & IDs
        for v in vehicles:
            x1, y1, x2, y2 = [int(coord) for coord in v.bbox]
            raw_c = v.color
            color = (int(raw_c[0]), int(raw_c[1]), int(raw_c[2]))

            if self.overlay_options["show_boxes"]:
                # Draw rounded-corner look bounding box with corner highlights
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Corner accents
                c_len = max(5, min(15, (x2 - x1) // 3, (y2 - y1) // 3))
                accent_color = (255, 255, 255)
                # Top-left
                cv2.line(frame, (x1, y1), (x1 + c_len, y1), accent_color, 2)
                cv2.line(frame, (x1, y1), (x1 + c_len, y1), accent_color, 2)
                # Bottom-right
                cv2.line(frame, (x2, y2), (x2 - c_len, y2), accent_color, 2)
                cv2.line(frame, (x2, y2), (x2 - c_len, y2), accent_color, 2)

            # Centroid point
            c_pt = (int(v.centroid[0]), int(v.centroid[1]))
            cv2.circle(frame, c_pt, 4, (0, 255, 255), -1)

            # Label Pill
            if self.overlay_options["show_labels"] or self.overlay_options["show_ids"]:
                parts = []
                if self.overlay_options["show_ids"]:
                    parts.append(f"#{v.track_id}")
                if self.overlay_options["show_labels"]:
                    parts.append(f"{v.class_name.title()} {int(v.confidence*100)}%")
                if self.overlay_options["show_speed"] and v.speed_kmh > 0:
                    parts.append(f"{v.speed_kmh}km/h")

                tag = " | ".join(parts)
                tag_w = int(len(tag) * 7.5) + 12
                tag_y1 = int(max(18, y1 - 18))
                tag_y2 = int(y1)

                cv2.rectangle(frame, (x1, tag_y1), (x1 + tag_w, tag_y2), (20, 24, 30), -1)
                cv2.rectangle(frame, (x1, tag_y1), (x1 + tag_w, tag_y2), color, 1)
                cv2.putText(frame, tag, (x1 + 6, tag_y2 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

        # 4. Top Heads-Up Display (HUD) Banner
        if self.overlay_options["show_density_hud"]:
            hud_h = 42
            hud_bg = frame[:hud_h, :].copy()
            cv2.rectangle(frame, (0, 0), (w, hud_h), (12, 16, 24), -1)
            cv2.addWeighted(frame[:hud_h, :], 0.85, hud_bg, 0.15, 0, frame[:hud_h, :])
            cv2.line(frame, (0, hud_h), (w, hud_h), (50, 65, 85), 1)

            # Left stats: FPS, Source, Active Count
            fps_text = f"FPS: {self.current_fps:.1f}"
            cnt_text = f"ACTIVE IN SCENE: {len(vehicles)}"
            cum_text = f"TOTAL TRACKED: {self.tracker.total_tracked_cumulative}"
            
            cv2.putText(frame, fps_text, (18, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 2)
            cv2.putText(frame, cnt_text, (130, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            cv2.putText(frame, cum_text, (340, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 220, 255), 1)

            # Right stats: Overall Density Indicator
            d_cat = overall["overall_density_category"]
            d_score = overall["overall_density_score"]
            d_text = f"DENSITY: {d_cat.upper()} ({d_score}%)"
            
            d_color = (0, 255, 100) if d_cat == "Low" else ((0, 180, 255) if d_cat == "Medium" else (0, 50, 255))
            cv2.rectangle(frame, (w - 240, 8), (w - 15, 34), (25, 30, 42), -1)
            cv2.rectangle(frame, (w - 240, 8), (w - 15, 34), d_color, 1)
            cv2.circle(frame, (w - 225, 21), 6, d_color, -1)
            cv2.putText(frame, d_text, (w - 212, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

        return frame

    def toggle_overlay(self, key: str) -> bool:
        if key in self.overlay_options:
            self.overlay_options[key] = not self.overlay_options[key]
            return self.overlay_options[key]
        return False
