"""
Sample Traffic Video Downloader and Synthetic Video Generator
Ensures high-quality traffic video inputs are always available out of the box.
"""
import os
import cv2
import numpy as np
import urllib.request
import math
import random

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
os.makedirs(SAMPLE_DIR, exist_ok=True)


def download_sample_video(url: str, output_path: str) -> bool:
    """Download an open sample traffic video if reachable."""
    if os.path.exists(output_path) and os.path.getsize(output_path) > 100000:
        print(f"[SampleManager] Video already exists: {output_path}")
        return True
    try:
        print(f"[SampleManager] Downloading sample video from {url}...")
        urllib.request.urlretrieve(url, output_path)
        print(f"[SampleManager] Downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"[SampleManager] Download failed ({e}), generating synthetic traffic video instead.")
        return False


def generate_synthetic_highway_video(output_path: str, duration_sec: int = 15, fps: int = 30):
    """
    Generates a realistic 1280x720 multi-lane highway traffic video with
    cars, trucks, buses, motorcycles moving down and up lanes.
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 50000:
        print(f"[SampleManager] Video already exists: {output_path}")
        return

    print(f"[SampleManager] Generating realistic synthetic traffic video: {output_path}...")
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps

    # Vehicle types and specifications
    vehicle_types = [
        {"type": "car", "w": 42, "h": 76, "color": (40, 40, 220), "speed_range": (5, 9)},
        {"type": "car", "w": 40, "h": 72, "color": (220, 200, 40), "speed_range": (6, 10)},
        {"type": "car", "w": 44, "h": 78, "color": (220, 220, 220), "speed_range": (5, 8)},
        {"type": "car", "w": 42, "h": 74, "color": (30, 30, 30), "speed_range": (6, 9)},
        {"type": "truck", "w": 52, "h": 140, "color": (30, 140, 200), "speed_range": (3, 6)},
        {"type": "bus", "w": 50, "h": 130, "color": (0, 165, 255), "speed_range": (4, 7)},
        {"type": "motorcycle", "w": 20, "h": 44, "color": (180, 50, 180), "speed_range": (7, 11)}
    ]

    lanes_x = [380, 510, 640, 770, 900] # 4 lanes

    active_vehicles = []

    def spawn_vehicle(lane_idx):
        v_spec = random.choice(vehicle_types).copy()
        x_center = (lanes_x[lane_idx] + lanes_x[lane_idx + 1]) // 2
        speed = random.uniform(*v_spec["speed_range"])
        return {
            "type": v_spec["type"],
            "x": x_center - v_spec["w"] // 2 + random.randint(-5, 5),
            "y": -v_spec["h"] - random.randint(10, 100),
            "w": v_spec["w"],
            "h": v_spec["h"],
            "color": v_spec["color"],
            "speed": speed,
            "lane": lane_idx + 1
        }

    # Initial spawns
    for lane_i in range(len(lanes_x) - 1):
        for init_y in range(100, height - 100, 180):
            v = spawn_vehicle(lane_i)
            v["y"] = init_y + random.randint(-40, 40)
            active_vehicles.append(v)

    road_dash_offset = 0

    for frame_idx in range(total_frames):
        # Background: Green roadside + dark asphalt highway
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (45, 110, 45) # Grass roadside

        # Road asphalt
        road_left = 320
        road_right = 960
        frame[:, road_left:road_right] = (48, 50, 54) # Asphalt

        # Shoulder lines (solid yellow left, solid white right)
        cv2.line(frame, (road_left + 10, 0), (road_left + 10, height), (0, 215, 255), 4) # Yellow
        cv2.line(frame, (road_right - 10, 0), (road_right - 10, height), (240, 240, 240), 4) # White

        # Dashed lane markings
        road_dash_offset = (road_dash_offset + 8) % 40
        for lx in lanes_x[1:-1]:
            for y_pos in range(-40 + int(road_dash_offset), height, 40):
                cv2.line(frame, (lx, y_pos), (lx, y_pos + 20), (230, 230, 230), 2)

        # Update & draw vehicles
        for v in active_vehicles:
            v["y"] += v["speed"]

            vx, vy, vw, vh = int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"])

            # Shadow
            cv2.rectangle(frame, (vx + 4, vy + 4), (vx + vw + 4, vy + vh + 4), (25, 25, 25), -1)

            # Vehicle body
            cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), v["color"], -1)
            cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (20, 20, 20), 2)

            # Windshields & roof details
            if v["type"] == "car":
                # Front windshield
                cv2.rectangle(frame, (vx + 4, vy + 12), (vx + vw - 4, vy + 24), (100, 160, 200), -1)
                # Rear windshield
                cv2.rectangle(frame, (vx + 4, vy + vh - 22), (vx + vw - 4, vy + vh - 12), (70, 120, 150), -1)
                # Roof
                cv2.rectangle(frame, (vx + 6, vy + 25), (vx + vw - 6, vy + vh - 23),
                              tuple(max(0, c - 30) for c in v["color"]), -1)
                # Headlights
                cv2.rectangle(frame, (vx + 2, vy + 2), (vx + 8, vy + 6), (200, 255, 255), -1)
                cv2.rectangle(frame, (vx + vw - 8, vy + 2), (vx + vw - 2, vy + 6), (200, 255, 255), -1)
                # Tail lights
                cv2.rectangle(frame, (vx + 2, vy + vh - 5), (vx + 8, vy + vh - 2), (0, 0, 220), -1)
                cv2.rectangle(frame, (vx + vw - 8, vy + vh - 5), (vx + vw - 2, vy + vh - 2), (0, 0, 220), -1)

            elif v["type"] in ["truck", "bus"]:
                # Cab / Front window
                cv2.rectangle(frame, (vx + 4, vy + 6), (vx + vw - 4, vy + 22), (90, 150, 190), -1)
                # Cargo body or roof
                cv2.rectangle(frame, (vx + 3, vy + 26), (vx + vw - 3, vy + vh - 8),
                              tuple(max(0, c - 20) for c in v["color"]), -1)
                # Tail lights
                cv2.rectangle(frame, (vx + 2, vy + vh - 4), (vx + 10, vy + vh - 1), (0, 0, 240), -1)
                cv2.rectangle(frame, (vx + vw - 10, vy + vh - 4), (vx + vw - 2, vy + vh - 1), (0, 0, 240), -1)

            elif v["type"] == "motorcycle":
                # Rider helmet & handles
                cv2.circle(frame, (vx + vw // 2, vy + vh // 2), 6, (240, 240, 50), -1)
                cv2.line(frame, (vx + 2, vy + 10), (vx + vw - 2, vy + 10), (10, 10, 10), 2)

        # Remove vehicles that left screen and respawn
        active_vehicles = [v for v in active_vehicles if v["y"] < height + 100]

        for lane_i in range(len(lanes_x) - 1):
            lane_vehicles = [v for v in active_vehicles if v["lane"] == lane_i + 1]
            if not lane_vehicles or min(v["y"] for v in lane_vehicles) > 120:
                if random.random() < 0.35:
                    active_vehicles.append(spawn_vehicle(lane_i))

        # Lane numbers indicator
        for idx, lx in enumerate(lanes_x[:-1]):
            lane_center_x = (lx + lanes_x[idx + 1]) // 2
            cv2.putText(frame, f"LANE {idx+1}", (lane_center_x - 30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        out.write(frame)

    out.release()
    print(f"[SampleManager] Generated highway video successfully: {output_path}")


def prepare_sample_videos():
    """Ensure standard sample traffic videos are ready."""
    sample_1 = os.path.join(SAMPLE_DIR, "highway_traffic.mp4")
    sample_2 = os.path.join(SAMPLE_DIR, "urban_intersection.mp4")

    # Try downloading real sample traffic clip if available
    download_sample_video(
        "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4",
        sample_2
    )

    # Always generate guaranteed procedural realistic highway video
    generate_synthetic_highway_video(sample_1, duration_sec=20, fps=25)


if __name__ == "__main__":
    prepare_sample_videos()
