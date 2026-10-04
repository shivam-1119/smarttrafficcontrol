"""
Phase 4: Multi-Lane / ROI Polygon System & Lane-wise Counting
Provides customizable lane zones, point-in-polygon containment,
virtual line-crossing counters, per-lane vehicle classification statistics,
and fully adjustable lane width & perspective configuration.
"""
import numpy as np
import cv2
from typing import List, Dict, Any, Tuple, Optional
from shapely.geometry import Point, Polygon, LineString

LANE_PALETTE = [
    {"fill": (255, 100, 0, 45), "border": (255, 120, 30), "name": "Cyan-Blue"},
    {"fill": (0, 220, 100, 45), "border": (30, 240, 120), "name": "Emerald"},
    {"fill": (200, 50, 255, 45), "border": (220, 80, 255), "name": "Purple"},
    {"fill": (0, 160, 255, 45), "border": (0, 190, 255), "name": "Orange"},
    {"fill": (255, 220, 0, 45), "border": (255, 235, 50), "name": "Yellow"},
    {"fill": (50, 50, 255, 45), "border": (80, 80, 255), "name": "Red"},
    {"fill": (0, 235, 255, 45), "border": (0, 255, 255), "name": "Aqua"}
]


class LaneROI:
    def __init__(self, lane_id: str, name: str, polygon_pts: List[List[int]], 
                 count_line: Optional[List[List[int]]] = None, capacity: int = 8, color_idx: int = 0):
        self.lane_id = lane_id
        self.name = name
        self.polygon_pts = polygon_pts # [[x1, y1], [x2, y2], ...]
        self.count_line = count_line   # [[x1, y1], [x2, y2]]
        self.capacity = capacity
        
        color_info = LANE_PALETTE[color_idx % len(LANE_PALETTE)]
        self.fill_color = color_info["fill"]
        self.border_color = color_info["border"]
        
        self.polygon = Polygon(self.polygon_pts) if len(self.polygon_pts) >= 3 else None
        self.line = LineString(self.count_line) if self.count_line and len(self.count_line) == 2 else None
        
        # Lane State
        self.active_vehicle_ids: List[int] = []
        self.cumulative_counts: Dict[str, int] = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
            "bicycle": 0,
            "person": 0,
            "total": 0
        }
        self.passed_vehicle_ids: set = set()

    def update_geometry(self, polygon_pts: List[List[int]], count_line: Optional[List[List[int]]] = None):
        self.polygon_pts = polygon_pts
        self.polygon = Polygon(self.polygon_pts) if len(self.polygon_pts) >= 3 else None
        if count_line:
            self.count_line = count_line
            self.line = LineString(self.count_line) if len(self.count_line) == 2 else None

    def contains_point(self, pt: Tuple[int, int]) -> bool:
        if self.polygon is None:
            return False
        point = Point(pt[0], pt[1])
        return self.polygon.contains(point) or self.polygon.touches(point)

    def check_line_crossing(self, prev_pt: Tuple[int, int], curr_pt: Tuple[int, int]) -> bool:
        """Detects if a vehicle trajectory segment crossed this lane's trigger line."""
        if self.line is None:
            return False
        traj_line = LineString([prev_pt, curr_pt])
        return self.line.intersects(traj_line)

    def record_passage(self, track_id: int, class_name: str):
        if track_id not in self.passed_vehicle_ids:
            self.passed_vehicle_ids.add(track_id)
            c_key = class_name.lower()
            if c_key in self.cumulative_counts:
                self.cumulative_counts[c_key] += 1
            else:
                self.cumulative_counts["car"] += 1
            self.cumulative_counts["total"] += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "name": self.name,
            "polygon_pts": self.polygon_pts,
            "count_line": self.count_line,
            "capacity": self.capacity,
            "active_count": len(self.active_vehicle_ids),
            "active_vehicle_ids": list(self.active_vehicle_ids),
            "cumulative_counts": self.cumulative_counts,
            "border_color": list(self.border_color),
            "occupancy_ratio": round(len(self.active_vehicle_ids) / max(1, self.capacity), 2)
        }


class LaneManager:
    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.lanes: Dict[str, LaneROI] = {}
        self.current_preset = "4_lane_highway"
        
        # Adjustable Road Configuration State (in percentages 0 - 100)
        self.road_config = {
            "lane_count": 4,
            "top_left_pct": 16.0,
            "top_right_pct": 76.0,
            "bottom_left_pct": 4.0,
            "bottom_right_pct": 82.0,
            "top_y_pct": 5.0,
            "bottom_y_pct": 96.0,
            "trigger_y_pct": 62.0,
            "lane_width_weights": [25.0, 25.0, 25.0, 25.0]
        }
        
        self.apply_road_config(self.road_config)

    def apply_road_config(self, config: Dict[str, Any]):
        """
        Calculates and generates multi-lane polygons with perspective & adjustable widths.
        Allows full user control over road boundaries, lane count, and individual divider positions.
        """
        w, h = self.frame_width, self.frame_height
        self.road_config.update(config)
        
        lane_count = max(1, min(7, int(self.road_config.get("lane_count", 4))))
        top_l_pct = float(self.road_config.get("top_left_pct", 16.0))
        top_r_pct = float(self.road_config.get("top_right_pct", 76.0))
        bot_l_pct = float(self.road_config.get("bottom_left_pct", 4.0))
        bot_r_pct = float(self.road_config.get("bottom_right_pct", 82.0))
        
        top_y_pct = float(self.road_config.get("top_y_pct", 5.0))
        bot_y_pct = float(self.road_config.get("bottom_y_pct", 96.0))
        trig_y_pct = float(self.road_config.get("trigger_y_pct", 62.0))
        
        weights = self.road_config.get("lane_width_weights", [])
        if len(weights) != lane_count or sum(weights) <= 0:
            weights = [100.0 / lane_count] * lane_count
            self.road_config["lane_width_weights"] = weights
            
        # Normalize weights
        total_w = sum(weights)
        norm_weights = [wt / total_w for wt in weights]
        
        # Calculate cumulative fractions across road width
        cum_fractions = [0.0]
        curr = 0.0
        for nw in norm_weights:
            curr += nw
            cum_fractions.append(curr)
        cum_fractions[-1] = 1.0 # Ensure last is exactly 1.0

        top_y = int(h * (top_y_pct / 100.0))
        bot_y = int(h * (bot_y_pct / 100.0))
        trig_y = int(h * (trig_y_pct / 100.0))
        
        top_l_x = int(w * (top_l_pct / 100.0))
        top_r_x = int(w * (top_r_pct / 100.0))
        bot_l_x = int(w * (bot_l_pct / 100.0))
        bot_r_x = int(w * (bot_r_pct / 100.0))

        # Preserve existing counts if same lane_ids
        old_lanes = dict(self.lanes)
        self.lanes.clear()

        for i in range(lane_count):
            f_left = cum_fractions[i]
            f_right = cum_fractions[i+1]
            
            # Interpolate top points
            tl_x = int(top_l_x + (top_r_x - top_l_x) * f_left)
            tr_x = int(top_l_x + (top_r_x - top_l_x) * f_right)
            
            # Interpolate bottom points
            bl_x = int(bot_l_x + (bot_r_x - bot_l_x) * f_left)
            br_x = int(bot_l_x + (bot_r_x - bot_l_x) * f_right)
            
            # Interpolate trigger line points at trig_y
            t_ratio = (trig_y - top_y) / max(1, (bot_y - top_y))
            line_l_x = int(tl_x + (bl_x - tl_x) * t_ratio)
            line_r_x = int(tr_x + (br_x - tr_x) * t_ratio)

            polygon_pts = [
                [tl_x, top_y],
                [tr_x, top_y],
                [br_x, bot_y],
                [bl_x, bot_y]
            ]
            
            count_line = [
                [line_l_x, trig_y],
                [line_r_x, trig_y]
            ]
            
            lane_id = f"lane_{i+1}"
            lane_name = f"Lane {i+1}"
            if lane_count == 4:
                descriptors = ["Far Left / Incoming", "Mid Left", "Mid Right", "Right Curb / Exit"]
                lane_name = f"Lane {i+1} ({descriptors[i]})"

            new_lane = LaneROI(
                lane_id=lane_id,
                name=lane_name,
                polygon_pts=polygon_pts,
                count_line=count_line,
                capacity=8,
                color_idx=i
            )

            # Carry over counts if exists
            if lane_id in old_lanes:
                new_lane.cumulative_counts = old_lanes[lane_id].cumulative_counts
                new_lane.passed_vehicle_ids = old_lanes[lane_id].passed_vehicle_ids

            self.lanes[lane_id] = new_lane

    def load_preset(self, preset_name: str):
        """Loads predefined lane configurations and updates road_config."""
        self.current_preset = preset_name
        
        if preset_name == "4_lane_highway" or preset_name == "4_lane_full_road":
            self.road_config = {
                "lane_count": 4,
                "top_left_pct": 16.0,
                "top_right_pct": 76.0,
                "bottom_left_pct": 4.0,
                "bottom_right_pct": 82.0,
                "top_y_pct": 5.0,
                "bottom_y_pct": 96.0,
                "trigger_y_pct": 62.0,
                "lane_width_weights": [25.0, 25.0, 25.0, 25.0]
            }
        elif preset_name == "full_road_wide":
            self.road_config = {
                "lane_count": 4,
                "top_left_pct": 2.0,
                "top_right_pct": 98.0,
                "bottom_left_pct": 1.0,
                "bottom_right_pct": 99.0,
                "top_y_pct": 4.0,
                "bottom_y_pct": 96.0,
                "trigger_y_pct": 60.0,
                "lane_width_weights": [25.0, 25.0, 25.0, 25.0]
            }
        elif preset_name == "left_traffic_focus":
            self.road_config = {
                "lane_count": 3,
                "top_left_pct": 12.0,
                "top_right_pct": 55.0,
                "bottom_left_pct": 2.0,
                "bottom_right_pct": 55.0,
                "top_y_pct": 5.0,
                "bottom_y_pct": 95.0,
                "trigger_y_pct": 60.0,
                "lane_width_weights": [33.3, 33.3, 33.4]
            }
        elif preset_name == "right_traffic_focus":
            self.road_config = {
                "lane_count": 3,
                "top_left_pct": 38.0,
                "top_right_pct": 82.0,
                "bottom_left_pct": 32.0,
                "bottom_right_pct": 88.0,
                "top_y_pct": 5.0,
                "bottom_y_pct": 95.0,
                "trigger_y_pct": 60.0,
                "lane_width_weights": [33.3, 33.3, 33.4]
            }
        elif preset_name == "urban_intersection":
            self.road_config = {
                "lane_count": 4,
                "top_left_pct": 10.0,
                "top_right_pct": 90.0,
                "bottom_left_pct": 3.0,
                "bottom_right_pct": 92.0,
                "top_y_pct": 8.0,
                "bottom_y_pct": 95.0,
                "trigger_y_pct": 55.0,
                "lane_width_weights": [25.0, 25.0, 25.0, 25.0]
            }
        elif preset_name == "3_lane_express":
            self.road_config = {
                "lane_count": 3,
                "top_left_pct": 15.0,
                "top_right_pct": 78.0,
                "bottom_left_pct": 4.0,
                "bottom_right_pct": 82.0,
                "top_y_pct": 6.0,
                "bottom_y_pct": 95.0,
                "trigger_y_pct": 58.0,
                "lane_width_weights": [33.3, 33.3, 33.4]
            }
        elif preset_name == "dual_section" or preset_name == "default_split":
            self.road_config = {
                "lane_count": 2,
                "top_left_pct": 8.0,
                "top_right_pct": 88.0,
                "bottom_left_pct": 3.0,
                "bottom_right_pct": 92.0,
                "top_y_pct": 5.0,
                "bottom_y_pct": 95.0,
                "trigger_y_pct": 50.0,
                "lane_width_weights": [50.0, 50.0]
            }
            
        self.apply_road_config(self.road_config)

    def process_vehicles(self, vehicles: List[Any]):
        """
        Assigns each active vehicle to its containing lane ROI and evaluates line crossings.
        """
        # Clear active vehicle sets for new frame
        for lane in self.lanes.values():
            lane.active_vehicle_ids.clear()

        for v in vehicles:
            centroid = (int(v.centroid[0]), int(v.centroid[1]))
            assigned = False

            for lane_id, lane in self.lanes.items():
                if lane.contains_point(centroid):
                    lane.active_vehicle_ids.append(v.track_id)
                    v.lane_id = lane_id
                    v.lane_name = lane.name
                    assigned = True

                    # Check virtual line crossing
                    if len(v.history) >= 2:
                        prev_pt = (int(v.history[-2][0]), int(v.history[-2][1]))
                        if lane.check_line_crossing(prev_pt, centroid):
                            lane.record_passage(v.track_id, v.class_name)
                            v.has_counted = True
                    break

            if not assigned:
                v.lane_id = None
                v.lane_name = "Outside ROI"

    def set_custom_lane(self, lane_id: str, name: str, polygon_pts: List[List[int]], 
                        count_line: Optional[List[List[int]]] = None, capacity: int = 8):
        """Creates or updates an individual custom lane definition."""
        if lane_id in self.lanes:
            lane = self.lanes[lane_id]
            lane.name = name
            lane.capacity = capacity
            lane.update_geometry(polygon_pts, count_line)
        else:
            color_idx = len(self.lanes)
            self.lanes[lane_id] = LaneROI(lane_id, name, polygon_pts, count_line, capacity, color_idx)

    def remove_lane(self, lane_id: str):
        if lane_id in self.lanes:
            del self.lanes[lane_id]

    def reset_counts(self):
        for lane in self.lanes.values():
            for k in lane.cumulative_counts:
                lane.cumulative_counts[k] = 0
            lane.passed_vehicle_ids.clear()
            lane.active_vehicle_ids.clear()

    def get_summary(self) -> Dict[str, Any]:
        return {
            "preset": self.current_preset,
            "total_lanes": len(self.lanes),
            "road_config": self.road_config,
            "lanes": [lane.to_dict() for lane in self.lanes.values()]
        }
