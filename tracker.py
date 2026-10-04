"""
Phase 3: Vehicle Tracking & Trajectory Analysis Module
Assigns persistent Track IDs across frames, maintains motion history paths,
estimates vehicle velocities, heading directions, and tracks spatial longevity.
"""
import numpy as np
import time
import math
from typing import List, Dict, Any, Tuple, Optional
from collections import deque


def compute_iou(boxA, boxB):
    # box: [x1, y1, x2, y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou


class TrackedVehicle:
    def __init__(self, track_id: int, detection: Dict[str, Any], max_history: int = 30):
        self.track_id = track_id
        self.class_id = detection["class_id"]
        self.class_name = detection["class_name"]
        self.color = detection["color"]
        self.bbox = detection["bbox"]
        self.centroid = detection["centroid"]
        self.confidence = detection["confidence"]
        self.width = detection["width"]
        self.height = detection["height"]
        
        self.history = deque(maxlen=max_history)
        self.history.append(self.centroid)
        
        self.timestamps = deque(maxlen=max_history)
        self.timestamps.append(time.time())
        
        self.created_at = time.time()
        self.last_updated = time.time()
        self.frames_inactive = 0
        self.total_frames_active = 1
        
        self.speed_kmh = 0.0
        self.direction = "Stationary"
        self.vx = 0.0
        self.vy = 0.0
        self.lane_id: Optional[str] = None
        self.lane_name: Optional[str] = None
        self.has_counted: bool = False

    def update(self, detection: Dict[str, Any]):
        self.bbox = detection["bbox"]
        self.centroid = detection["centroid"]
        self.confidence = detection["confidence"]
        self.width = detection["width"]
        self.height = detection["height"]
        
        now = time.time()
        self.history.append(self.centroid)
        self.timestamps.append(now)
        
        self.last_updated = now
        self.frames_inactive = 0
        self.total_frames_active += 1
        
        self._compute_motion()

    def _compute_motion(self):
        if len(self.history) < 3:
            return

        # Use recent 5-8 points for smoothed velocity
        p_curr = self.history[-1]
        p_prev = self.history[-min(len(self.history), 6)]
        t_curr = self.timestamps[-1]
        t_prev = self.timestamps[-min(len(self.timestamps), 6)]
        
        dt = max(0.001, t_curr - t_prev)
        dx = p_curr[0] - p_prev[0]
        dy = p_curr[1] - p_prev[1]
        
        dist_px = math.hypot(dx, dy)
        speed_px_sec = dist_px / dt
        
        # Approximate scale factor: 1 pixel ~ 0.05 meters (customizable)
        scale_m_per_px = 0.05
        speed_mps = speed_px_sec * scale_m_per_px
        self.speed_kmh = round(speed_mps * 3.6, 1)
        self.vx = round(dx / dt, 1)
        self.vy = round(dy / dt, 1)

        # Direction calculation
        if dist_px < 3.0:
            self.direction = "Stationary"
        else:
            angle = math.degrees(math.atan2(dy, dx))
            # Standard screen coordinates: y goes downwards
            if 45 <= angle <= 135:
                self.direction = "Southbound 🠗"
            elif -135 <= angle <= -45:
                self.direction = "Northbound 🠕"
            elif -45 < angle < 45:
                self.direction = "Eastbound 🠖"
            else:
                self.direction = "Westbound 🠔"

    def mark_inactive(self):
        self.frames_inactive += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "class_id": self.class_id,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "centroid": self.centroid,
            "width": self.width,
            "height": self.height,
            "speed_kmh": self.speed_kmh,
            "direction": self.direction,
            "lane_id": self.lane_id,
            "lane_name": self.lane_name or "Unassigned",
            "active_seconds": round(time.time() - self.created_at, 1),
            "history": list(self.history)[-15:] # Last 15 points for fast wire transfer
        }


class VehicleTracker:
    def __init__(self, max_inactive_frames: int = 15, iou_thresh: float = 0.3, max_distance_px: float = 120.0):
        self.next_track_id: int = 101
        self.tracked_vehicles: Dict[int, TrackedVehicle] = {}
        self.max_inactive_frames = max_inactive_frames
        self.iou_thresh = iou_thresh
        self.max_distance_px = max_distance_px
        self.total_tracked_cumulative: int = 0

    def update(self, detections: List[Dict[str, Any]]) -> List[TrackedVehicle]:
        """
        Matches incoming detections with existing tracks using Hungarian/Greedy IoU and Centroid distance.
        """
        current_tracks = list(self.tracked_vehicles.values())
        unmatched_detections = list(range(len(detections)))
        unmatched_tracks = list(self.tracked_vehicles.keys())
        matched_pairs = []

        if current_tracks and detections:
            # Build cost / similarity matrix
            cost_matrix = np.zeros((len(current_tracks), len(detections)))
            for t_idx, track in enumerate(current_tracks):
                for d_idx, det in enumerate(detections):
                    # Only match same class family (or vehicle types interchangeably)
                    cls_match = 1.0 if (track.class_name == det["class_name"] or 
                                       (track.class_name in ["car", "truck", "bus"] and det["class_name"] in ["car", "truck", "bus"])) else 0.4
                    
                    iou = compute_iou(track.bbox, det["bbox"])
                    c_dist = math.hypot(track.centroid[0] - det["centroid"][0], track.centroid[1] - det["centroid"][1])
                    dist_score = max(0.0, 1.0 - (c_dist / self.max_distance_px))
                    
                    similarity = (0.55 * iou + 0.45 * dist_score) * cls_match
                    cost_matrix[t_idx, d_idx] = similarity

            # Greedy matching from highest similarity
            while True:
                max_val = np.max(cost_matrix) if cost_matrix.size > 0 else 0
                if max_val < self.iou_thresh:
                    break
                t_idx, d_idx = np.unravel_index(np.argmax(cost_matrix), cost_matrix.shape)
                track_id = current_tracks[t_idx].track_id
                
                matched_pairs.append((track_id, d_idx))
                
                if track_id in unmatched_tracks:
                    unmatched_tracks.remove(track_id)
                if d_idx in unmatched_detections:
                    unmatched_detections.remove(d_idx)
                    
                cost_matrix[t_idx, :] = -1
                cost_matrix[:, d_idx] = -1

        # Update matched tracks
        for track_id, d_idx in matched_pairs:
            self.tracked_vehicles[track_id].update(detections[d_idx])

        # Mark unmatched tracks as inactive
        for track_id in unmatched_tracks:
            self.tracked_vehicles[track_id].mark_inactive()

        # Create new tracks for unmatched detections
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            new_vehicle = TrackedVehicle(self.next_track_id, det)
            self.tracked_vehicles[self.next_track_id] = new_vehicle
            self.next_track_id += 1
            self.total_tracked_cumulative += 1

        # Purge dead tracks that have been inactive for too long
        dead_ids = [
            t_id for t_id, vehicle in self.tracked_vehicles.items()
            if vehicle.frames_inactive > self.max_inactive_frames
        ]
        for t_id in dead_ids:
            del self.tracked_vehicles[t_id]

        # Return list of currently active vehicles
        return [v for v in self.tracked_vehicles.values() if v.frames_inactive == 0]

    def reset(self):
        self.tracked_vehicles.clear()
        self.next_track_id = 101
        self.total_tracked_cumulative = 0
