# Smart Traffic Control & Real-Time Vision AI

A state-of-the-art Computer Vision & Traffic Density Optimization System powered by **YOLOv8**, **Multi-Object Tracking**, **Polygon Lane ROI Analysis**, and an **Adaptive Traffic Signal Controller** with an interactive **FastAPI & Glassmorphic Web Dashboard**.

---

## 🚀 Key Modules & System Architecture (5 Phases)

### 🔹 Phase 1: Video Ingestion & Camera Input Management (`video_manager.py`)
- **Live Camera Auto-Discovery:** Automatically scans and interfaces with physical webcams and USB cameras (`Camera 0, 1, 2...`).
- **Sample Traffic Video Catalog:** Includes pre-packaged high-definition real-world urban intersection and synthetic multi-lane highway videos.
- **Custom Video Uploader:** Drag-and-drop support for `.mp4`, `.avi`, `.mov`, and `.mkv` files.
- **RTSP / IP Camera Support:** Connects directly to external CCTV and network video streams.
- **Threaded Stream Processor:** Smooth frame-rate throttling, loop management, and frame synchronization.

### 🔹 Phase 2: YOLO Vehicle Detection Engine (`detector.py`)
- **Neural Network Architecture:** Utilizes Ultralytics YOLOv8 neural network (`yolov8n.pt`).
- **Target Classes Detected:** Cars, Motorcycles, Buses, Trucks, Bicycles, Pedestrians, Traffic Lights.
- **Precision Spatial Localization:** Extracts bounding boxes `[x1, y1, x2, y2]`, centroid coordinates `(cx, cy)`, confidence scores, and vehicle dimensions in real time.
- **Dynamic Confidence Control:** Live sensitivity slider in the frontend from 10% to 95%.

### 🔹 Phase 3: Multi-Object Tracking & Trajectory Analysis (`tracker.py`)
- **Persistent Track Identification:** Assigns unique, persistent vehicle IDs across consecutive frames.
- **Trajectory History Paths:** Maintains smooth 30-frame motion trails to visualize path history and lane changes.
- **Speed & Heading Estimation:** Calculates real-time vehicle velocity vectors $(v_x, v_y)$, speed in km/h, and movement headings (*Northbound*, *Southbound*, *Eastbound*, *Westbound*, *Stationary*).
- **Stopped / Congestion Detection:** Identifies stalled or queued vehicles causing bottlenecks.

### 🔹 Phase 4: Multi-Lane / ROI System & Density Calculation (`lane_manager.py`, `density_engine.py`)
- **Interactive Multi-Zone ROI:** Configurable polygon zones for Lane 1, Lane 2, Lane 3, Lane 4, expressways, and intersections.
- **Point-in-Polygon Assignment:** Fast spatial ray-casting to assign every vehicle centroid to its exact lane.
- **Virtual Counting Lines:** Directional trigger lines calculating cumulative vehicle throughput split by vehicle class.
- **Composite Density Index:**
  - **Low Density (🟢 0-35%):** Free-flowing traffic.
  - **Medium Density (🟡 36-70%):** Moderate vehicular load.
  - **High Density (🔴 71-88%):** Dense queue formation.
  - **Severe / Congested (🚨 89%+):** Gridlock alert triggering automated green-wave priority.
- **Adaptive Traffic Signal Controller:** Dynamic green light duration calculator (15s to 120s) with 3-phase animated signal state machine (Red, Yellow, Green).

### 🔹 Phase 5: Interactive Web Dashboard & Real-Time Full-Stack Application (`app.py`, `templates/`, `static/`)
- **High-Performance MJPEG Stream:** Smooth low-latency video feed with toggleable overlay elements (bounding boxes, class labels, IDs, speed tags, lane polygons, counting triggers, and HUD).
- **WebSocket Telemetry Stream:** 12 Hz bi-directional JSON pipe for instant telemetry, metrics, and logs.
- **Interactive Canvas ROI Editor:** Click-and-drag lane polygon vertex repositioning directly on top of the live video feed.
- **Live Analytics Charts:** Chart.js real-time density trend graphs and vehicle classification doughnut charts.
- **Spatial Coordinates & Detection Logs:** Searchable real-time table with CSV and JSON data export.

---

## 🛠️ Installation & Setup

1. **Install Python 3.10+ (Python 3.13 / 3.14 supported)**
2. **Install Required Libraries:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Generate/Prepare Sample Videos:**
   ```bash
   py -3.13 sample_data_generator.py
   ```
4. **Launch Application Server:**
   ```bash
   py -3.13 app.py
   ```
   *Or double click `run_app.bat` on Windows.*

5. **Open in Browser:**
   Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📡 REST API & WebSocket Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Main interactive web dashboard |
| `/video_feed` | `GET` | MJPEG real-time annotated video stream |
| `/ws/traffic-stats` | `WebSocket` | Real-time JSON telemetry stream (~12 Hz) |
| `/api/sources` | `GET` | Catalog of webcams, sample clips, and uploads |
| `/api/set-source` | `POST` | Switch active camera/video source |
| `/api/upload-video` | `POST` | Upload and activate custom video file |
| `/api/lanes` | `GET` | Get current lane polygons and capacities |
| `/api/lanes/preset` | `POST` | Load geometry preset (highway, intersection, etc.) |
| `/api/lanes/custom` | `POST` | Save custom polygon coordinates from canvas editor |
| `/api/lanes/reset-counts`| `POST` | Reset cumulative counters and tracking history |
| `/api/toggle-overlay` | `POST` | Toggle bounding boxes, labels, IDs, trails, lanes |
| `/api/set-confidence` | `POST` | Adjust YOLO detection threshold |
| `/api/playback/toggle-pause` | `POST` | Pause / resume video stream |
| `/api/snapshot` | `GET` | Download current annotated high-res JPEG snapshot |
| `/api/export-logs` | `GET` | Export detection records in CSV or JSON format |
