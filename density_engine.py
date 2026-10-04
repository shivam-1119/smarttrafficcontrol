"""
Phase 4: Traffic Density Calculation & Adaptive Signal Timing Engine
Calculates real-time density indices (Low/Medium/High/Severe) and
provides dynamic traffic light cycle optimization and signal advisory.
"""
import time
from typing import Dict, List, Any, Optional


class TrafficDensityEngine:
    def __init__(self):
        self.signal_cycle_active: bool = True
        self.active_green_lane_id: Optional[str] = None
        self.signal_state: str = "GREEN" # "GREEN", "YELLOW", "RED"
        self.phase_start_time: float = time.time()
        self.phase_duration: float = 30.0 # seconds
        self.yellow_duration: float = 4.0 # seconds
        self.signal_plan: Dict[str, Dict[str, Any]] = {}
        self.history_records: List[Dict[str, Any]] = []

    def calculate_lane_density(self, lane_dict: Dict[str, Any], lane_vehicles: List[Any]) -> Dict[str, Any]:
        """
        Calculates comprehensive density metrics for a single lane.
        """
        active_count = lane_dict["active_count"]
        capacity = max(1, lane_dict["capacity"])
        occupancy_ratio = min(1.0, active_count / capacity)

        # Average speed and stopped vehicle analysis
        speeds = [v.speed_kmh for v in lane_vehicles if hasattr(v, "speed_kmh")]
        avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
        stopped_vehicles = sum(1 for v in lane_vehicles if getattr(v, "speed_kmh", 0) < 5.0)

        # Compute composite density score (0 to 100)
        # Factor 1: Vehicle Occupancy vs Capacity (0 to 70 pts)
        occ_score = occupancy_ratio * 70.0
        
        # Factor 2: Queue / stopped vehicles penalty (0 to 20 pts)
        queue_score = min(20.0, (stopped_vehicles / capacity) * 20.0)
        
        # Factor 3: Heavy vehicle weight (trucks/buses take more space)
        heavy_count = sum(1 for v in lane_vehicles if getattr(v, "class_name", "") in ["truck", "bus"])
        heavy_score = min(10.0, heavy_count * 3.5)

        raw_score = occ_score + queue_score + heavy_score
        density_score = min(100.0, round(raw_score, 1))

        # Density Category classification
        if density_score < 35.0:
            category = "Low"
            level_color = "#10b981" # Emerald Green
            status_text = "Free Flowing Traffic"
            recommended_green = 20
        elif density_score < 70.0:
            category = "Medium"
            level_color = "#f59e0b" # Amber / Yellow
            status_text = "Moderate Traffic"
            recommended_green = 45
        elif density_score < 88.0:
            category = "High"
            level_color = "#ef4444" # Bright Red
            status_text = "Dense Traffic - Heavy Queue"
            recommended_green = 75
        else:
            category = "Severe"
            level_color = "#881337" # Dark Maroon / Crimson
            status_text = "Congested / Gridlock Warning"
            recommended_green = 100

        return {
            "lane_id": lane_dict["lane_id"],
            "lane_name": lane_dict["name"],
            "active_count": active_count,
            "capacity": capacity,
            "density_score": density_score,
            "density_category": category,
            "color": level_color,
            "status_text": status_text,
            "avg_speed_kmh": avg_speed,
            "stopped_vehicles": stopped_vehicles,
            "heavy_vehicles": heavy_count,
            "recommended_green_sec": recommended_green
        }

    def update_signals(self, lanes_density: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Runs the dynamic traffic signal controller.
        Picks the highest demand lane, adjusts green phase time according to density.
        """
        now = time.time()
        lane_ids = [l["lane_id"] for l in lanes_density]

        if not lane_ids:
            return {"active_lane": None, "state": "RED", "remaining_sec": 0, "lanes": {}}

        if self.active_green_lane_id not in lane_ids:
            self.active_green_lane_id = lane_ids[0]
            self.phase_start_time = now
            self.signal_state = "GREEN"

        # Lookup current active lane density info
        active_lane_info = next((l for l in lanes_density if l["lane_id"] == self.active_green_lane_id), lanes_density[0])
        self.phase_duration = active_lane_info["recommended_green_sec"]

        elapsed = now - self.phase_start_time

        # State transition logic
        if self.signal_state == "GREEN":
            remaining = max(0, self.phase_duration - elapsed)
            if remaining <= 0:
                self.signal_state = "YELLOW"
                self.phase_start_time = now
                elapsed = 0
                remaining = self.yellow_duration

        elif self.signal_state == "YELLOW":
            remaining = max(0, self.yellow_duration - elapsed)
            if remaining <= 0:
                # Pick next lane: Prioritize lane with highest density score, or round-robin
                other_lanes = [l for l in lanes_density if l["lane_id"] != self.active_green_lane_id]
                if other_lanes:
                    # Sort by density descending
                    other_lanes.sort(key=lambda x: x["density_score"], reverse=True)
                    next_lane = other_lanes[0]["lane_id"]
                else:
                    next_lane = self.active_green_lane_id

                self.active_green_lane_id = next_lane
                self.signal_state = "GREEN"
                self.phase_start_time = now
                next_info = next((l for l in lanes_density if l["lane_id"] == next_lane), active_lane_info)
                self.phase_duration = next_info["recommended_green_sec"]
                remaining = self.phase_duration

        lane_signal_states = {}
        for l in lanes_density:
            lid = l["lane_id"]
            if lid == self.active_green_lane_id:
                state = self.signal_state # GREEN or YELLOW
            else:
                state = "RED"
            
            lane_signal_states[lid] = {
                "signal": state,
                "is_green": (state == "GREEN"),
                "is_yellow": (state == "YELLOW"),
                "is_red": (state == "RED"),
                "recommended_green_sec": l["recommended_green_sec"]
            }

        return {
            "active_green_lane": self.active_green_lane_id,
            "signal_state": self.signal_state,
            "remaining_seconds": int(max(0, (self.phase_duration if self.signal_state == "GREEN" else self.yellow_duration) - (now - self.phase_start_time))),
            "total_phase_seconds": int(self.phase_duration if self.signal_state == "GREEN" else self.yellow_duration),
            "lane_signals": lane_signal_states
        }

    def compute_overall_metrics(self, lanes_density: List[Dict[str, Any]], total_active: int) -> Dict[str, Any]:
        """Calculates macro intersection metrics."""
        if not lanes_density:
            return {
                "overall_density_category": "Low",
                "overall_density_score": 0.0,
                "overall_color": "#10b981",
                "total_active_vehicles": 0,
                "average_speed_kmh": 0.0,
                "congestion_alert": False
            }

        avg_score = sum(l["density_score"] for l in lanes_density) / len(lanes_density)
        avg_score = round(avg_score, 1)

        all_speeds = [l["avg_speed_kmh"] for l in lanes_density if l["avg_speed_kmh"] > 0]
        macro_speed = round(sum(all_speeds) / len(all_speeds), 1) if all_speeds else 0.0

        if avg_score < 35.0:
            category = "Low"
            color = "#10b981"
        elif avg_score < 70.0:
            category = "Medium"
            color = "#f59e0b"
        elif avg_score < 88.0:
            category = "High"
            color = "#ef4444"
        else:
            category = "Severe"
            color = "#881337"

        congestion_alert = (category in ["High", "Severe"]) or any(l["density_category"] == "Severe" for l in lanes_density)

        return {
            "overall_density_category": category,
            "overall_density_score": avg_score,
            "overall_color": color,
            "total_active_vehicles": total_active,
            "average_speed_kmh": macro_speed,
            "congestion_alert": congestion_alert
        }
