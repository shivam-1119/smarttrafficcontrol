"""
Phase 5: FastAPI Backend & Web Application Server
Exposes REST APIs, WebSocket real-time telemetry streaming,
and MJPEG video streaming for the Smart Traffic Vision Dashboard.
"""
import os
import cv2
import json
import time
import asyncio
import io
import csv
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import shutil

from pipeline import TrafficPipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="Smart Traffic Vision & Control AI", version="2.0.0")

# Mount static and template directories
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize Master Pipeline
pipeline = TrafficPipeline(model_name="yolov8n.pt", conf_thresh=0.35)

# Active WebSocket clients
connected_clients: List[WebSocket] = []


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Renders the interactive modern dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


def generate_mjpeg_stream():
    """Generates continuous MJPEG frames for the web stream."""
    while True:
        success, annotated_frame = pipeline.get_latest_frame()
        if not success or annotated_frame is None:
            time.sleep(0.03)
            continue

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            time.sleep(0.01)
            continue

        frame_bytes = jpeg.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.025) # ~30 FPS loop


@app.get("/video_feed")
async def video_feed():
    """MJPEG Video Feed Endpoint."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws/traffic-stats")
async def websocket_traffic_stats(websocket: WebSocket):
    """Streams real-time JSON telemetry metrics to connected frontends at ~12Hz."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            telemetry = pipeline.get_latest_telemetry()
            if telemetry:
                await websocket.send_text(json.dumps(telemetry))
            await asyncio.sleep(0.08) # ~12 updates per second
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception as e:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ==========================================
# REST API Endpoints
# ==========================================

@app.get("/api/sources")
async def get_sources():
    """Returns available camera devices, sample videos, and uploads."""
    return pipeline.video_manager.get_all_sources()


@app.post("/api/set-source")
async def set_source(source_type: str = Form(...), source_val: str = Form(...)):
    """Switches active camera or video input."""
    success = pipeline.video_manager.set_source(source_type, source_val)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to open selected video source")
    # Reset tracker and lane metrics for clean state
    pipeline.tracker.reset()
    pipeline.lane_manager.reset_counts()
    return {"status": "success", "message": f"Switched to {source_type}:{source_val}"}


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Uploads a custom traffic video file and automatically loads it."""
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="Only MP4, AVI, MOV, and MKV video formats are supported")

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Set as active source
    pipeline.video_manager.set_source("upload", file.filename)
    pipeline.tracker.reset()
    pipeline.lane_manager.reset_counts()
    return {"status": "success", "filename": file.filename, "message": "Video uploaded and activated"}


@app.get("/api/lanes")
async def get_lanes():
    """Returns lane configuration and geometries."""
    return pipeline.lane_manager.get_summary()


@app.post("/api/lanes/preset")
async def load_lane_preset(preset_name: str = Form(...)):
    """Loads a lane geometry preset ('4_lane_highway', 'urban_intersection', '3_lane_express')."""
    pipeline.lane_manager.load_preset(preset_name)
    pipeline.lane_manager.reset_counts()
    return {"status": "success", "preset": preset_name}


@app.post("/api/lanes/config")
async def update_road_config(config: Dict[str, Any]):
    """Updates road boundaries, lane widths, perspective tapering, and active lane count in real time."""
    pipeline.lane_manager.apply_road_config(config)
    return {"status": "success", "summary": pipeline.lane_manager.get_summary()}


@app.post("/api/lanes/custom")
async def save_custom_lane(data: Dict[str, Any]):
    """Creates or updates a custom lane definition."""
    lane_id = data.get("lane_id")
    name = data.get("name", "Custom Lane")
    poly = data.get("polygon_pts", [])
    count_line = data.get("count_line")
    capacity = data.get("capacity", 8)

    if not lane_id or len(poly) < 3:
        raise HTTPException(status_code=400, detail="Invalid lane geometry")

    pipeline.lane_manager.set_custom_lane(lane_id, name, poly, count_line, capacity)
    return {"status": "success", "lane_id": lane_id}


@app.delete("/api/lanes/{lane_id}")
async def delete_lane(lane_id: str):
    """Removes a lane ROI."""
    pipeline.lane_manager.remove_lane(lane_id)
    return {"status": "success", "lane_id": lane_id}


@app.post("/api/lanes/reset-counts")
async def reset_counts():
    """Resets cumulative vehicle counters."""
    pipeline.lane_manager.reset_counts()
    pipeline.tracker.reset()
    pipeline.recent_logs.clear()
    return {"status": "success", "message": "Counts and track logs reset successfully"}


@app.post("/api/toggle-overlay")
async def toggle_overlay(key: str = Form(...)):
    """Toggles visualization flags (show_boxes, show_labels, show_ids, show_trails, show_lanes, etc.)."""
    state = pipeline.toggle_overlay(key)
    return {"status": "success", "key": key, "new_state": state}


@app.post("/api/set-confidence")
async def set_confidence(confidence: float = Form(...)):
    """Adjusts YOLO detector confidence threshold."""
    pipeline.detector.set_confidence(confidence)
    return {"status": "success", "confidence": pipeline.detector.conf_threshold}


@app.post("/api/playback/toggle-pause")
async def toggle_pause():
    """Toggles playback pause / resume."""
    is_paused = pipeline.video_manager.toggle_pause()
    return {"status": "success", "is_paused": is_paused}


@app.get("/api/snapshot")
async def take_snapshot():
    """Captures and returns the current annotated frame as a high-quality JPEG."""
    ret, frame = pipeline.video_manager.read_frame()
    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="No active frame available")

    # Annotate frame
    _, annotated_frame, _ = pipeline.process_next_frame()
    if annotated_frame is None:
        annotated_frame = frame

    ret_enc, jpeg = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ret_enc:
        raise HTTPException(status_code=500, detail="Failed to encode image")

    return Response(content=jpeg.tobytes(), media_type="image/jpeg",
                    headers={"Content-Disposition": "attachment; filename=traffic_snapshot.jpg"})


@app.get("/api/export-logs")
async def export_logs(format: str = "json"):
    """Exports recent vehicle detection and tracking records as CSV or JSON."""
    logs = list(pipeline.recent_logs)
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Track_ID", "Class", "Lane", "Confidence", "Speed_KMH", "Direction", "BBox_X1_Y1_X2_Y2"])
        for entry in logs:
            writer.writerow([
                entry.get("timestamp", ""),
                entry.get("track_id", ""),
                entry.get("class_name", ""),
                entry.get("lane", ""),
                entry.get("confidence", ""),
                entry.get("speed_kmh", 0),
                entry.get("direction", ""),
                str(entry.get("bbox", ""))
            ])
        return Response(content=output.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=traffic_detections_log.csv"})

    return JSONResponse(content={"total_records": len(logs), "logs": logs})


if __name__ == "__main__":
    print("Starting Smart Traffic Vision Server on http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
