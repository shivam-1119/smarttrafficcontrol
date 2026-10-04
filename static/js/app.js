/**
 * Smart Traffic Vision AI - Main Application Script
 * Real-time WebSocket Telemetry, Charts, Signal Controllers & UI Interactions
 */

document.addEventListener("DOMContentLoaded", () => {
    // Initialize Lucide Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // App State
    let socket = null;
    let isPaused = false;
    let densityChart = null;
    let classDistChart = null;
    const densityHistory = [];
    const maxChartPoints = 30;

    // DOM Elements
    const hudFps = document.getElementById("hud-fps");
    const hudActive = document.getElementById("hud-total-active");
    const hudTracked = document.getElementById("hud-total-tracked");
    const wsStatusText = document.getElementById("ws-status-text");
    
    const densityCategory = document.getElementById("overall-density-category");
    const densityScore = document.getElementById("overall-density-score");
    const densityBarFill = document.getElementById("density-bar-fill");
    const congestionAlertBox = document.getElementById("congestion-alert-box");

    const signalRemainingTimer = document.getElementById("signal-remaining-timer");
    const laneSignalsContainer = document.getElementById("lane-signals-container");
    const lanesGridContainer = document.getElementById("lanes-grid-container");
    const totalLanesCount = document.getElementById("total-lanes-count");

    const detectionsTableBody = document.getElementById("detections-table-body");
    const tableSearchInput = document.getElementById("table-search-input");

    const selectVideoSource = document.getElementById("select-video-source");
    const selectLanePreset = document.getElementById("select-lane-preset");
    const inputVideoUpload = document.getElementById("input-video-upload");
    const uploadStatus = document.getElementById("upload-status");
    const sliderConfidence = document.getElementById("slider-confidence");
    const labelConfVal = document.getElementById("label-conf-val");
    const tagCurrentSource = document.getElementById("tag-current-source");

    // ==========================================
    // 1. WebSocket Telemetry Connection
    // ==========================================
    function connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/traffic-stats`;

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("[WebSocket] Connected to Real-time Traffic Telemetry");
            wsStatusText.textContent = "SYSTEM LIVE";
            wsStatusText.parentElement.style.borderColor = "rgba(16, 185, 129, 0.4)";
        };

        socket.onmessage = (event) => {
            try {
                const telemetry = JSON.parse(event.data);
                updateDashboard(telemetry);
            } catch (err) {
                console.error("[WebSocket] Parse Error:", err);
            }
        };

        socket.onclose = () => {
            console.warn("[WebSocket] Disconnected. Reconnecting in 2 seconds...");
            wsStatusText.textContent = "RECONNECTING...";
            wsStatusText.parentElement.style.borderColor = "rgba(239, 68, 68, 0.4)";
            setTimeout(connectWebSocket, 2000);
        };

        socket.onerror = (err) => {
            console.error("[WebSocket] Error:", err);
            socket.close();
        };
    }

    // ==========================================
    // 2. Real-time Dashboard UI Updates
    // ==========================================
    function updateDashboard(data) {
        if (!data) return;

        // Top HUD Metrics
        hudFps.textContent = (data.fps || 0).toFixed(1);
        hudActive.textContent = data.total_active_vehicles || 0;
        hudTracked.textContent = data.total_tracked_cumulative || 0;

        // Density Gauge & Overall Status
        const overall = data.overall_metrics || {};
        const cat = (overall.overall_density_category || "Low").toUpperCase();
        const score = overall.overall_density_score || 0;
        const color = overall.overall_color || "#10b981";

        densityCategory.textContent = `${cat} DENSITY`;
        densityCategory.className = `density-title text-${cat.toLowerCase()}`;
        densityScore.textContent = `${Math.round(score)}%`;
        densityBarFill.style.width = `${Math.min(100, Math.max(5, score))}%`;
        densityBarFill.style.backgroundColor = color;

        if (overall.congestion_alert) {
            congestionAlertBox.classList.remove("hidden");
        } else {
            congestionAlertBox.classList.add("hidden");
        }

        // Adaptive Traffic Signals
        const signals = data.signals || {};
        signalRemainingTimer.textContent = `${signals.remaining_seconds || 0}s`;
        renderTrafficSignals(signals, data.lanes_summary || []);

        // Lane Metrics Cards
        renderLaneCards(data.lanes_density || [], data.lanes_summary || []);

        // Update Charts
        updateCharts(data);

        // Update Detections Table
        renderDetectionsTable(data.recent_logs || []);
    }

    function renderTrafficSignals(signals, lanesSummary) {
        const laneSignals = signals.lane_signals || {};
        const activeGreenLane = signals.active_green_lane;

        let html = "";
        lanesSummary.forEach((lane) => {
            const lid = lane.lane_id;
            const sigInfo = laneSignals[lid] || { signal: "RED" };
            const state = sigInfo.signal || "RED";

            const isRed = state === "RED";
            const isYellow = state === "YELLOW";
            const isGreen = state === "GREEN";

            const pillClass = isGreen ? "pill-green" : (isYellow ? "pill-yellow" : "pill-red");
            const shortName = lane.name.split("(")[0].trim();

            html += `
                <div class="signal-housing-card">
                    <span class="signal-lane-name" title="${lane.name}">${shortName}</span>
                    <div class="traffic-light-rig">
                        <div class="light-lamp lamp-red ${isRed ? 'active' : ''}"></div>
                        <div class="light-lamp lamp-yellow ${isYellow ? 'active' : ''}"></div>
                        <div class="light-lamp lamp-green ${isGreen ? 'active' : ''}"></div>
                    </div>
                    <span class="signal-status-pill ${pillClass}">
                        ${state} ${isGreen ? `(${signals.remaining_seconds}s)` : ''}
                    </span>
                </div>
            `;
        });

        laneSignalsContainer.innerHTML = html;
    }

    function renderLaneCards(lanesDensity, lanesSummary) {
        totalLanesCount.textContent = `${lanesSummary.length} Zones`;
        let html = "";

        lanesSummary.forEach((lane, idx) => {
            const laneD = lanesDensity.find(d => d.lane_id === lane.lane_id) || {};
            const dCat = laneD.density_category || "Low";
            const catClass = `text-${dCat.toLowerCase()}`;
            const counts = lane.cumulative_counts || {};

            const borderColor = lane.border_color ? `rgb(${lane.border_color.join(',')})` : '#06b6d4';

            html += `
                <div class="lane-card" style="border-left-color: ${borderColor}">
                    <div class="lane-card-top">
                        <div class="lane-title-group">
                            <h4>${lane.name}</h4>
                        </div>
                        <span class="lane-badge-density ${catClass}">${dCat} (${laneD.density_score || 0}%)</span>
                    </div>
                    <div class="lane-card-body">
                        <div class="lane-stat-box">
                            <small>Occupancy</small><br>
                            <strong>${lane.active_count} / ${lane.capacity}</strong>
                        </div>
                        <div class="lane-stat-box">
                            <small>Total Passed</small><br>
                            <strong>${counts.total || 0} veh</strong>
                        </div>
                    </div>
                    <div class="lane-class-breakdown">
                        <span>🚗 ${counts.car || 0}</span>
                        <span>🏍️ ${counts.motorcycle || 0}</span>
                        <span>🚌 ${counts.bus || 0}</span>
                        <span>🚛 ${counts.truck || 0}</span>
                        <span>🚴 ${counts.bicycle || 0}</span>
                    </div>
                </div>
            `;
        });

        lanesGridContainer.innerHTML = html;
    }

    function renderDetectionsTable(logs) {
        const query = (tableSearchInput.value || "").toLowerCase();
        const filtered = logs.filter(item => {
            if (!query) return true;
            return (
                String(item.track_id).includes(query) ||
                (item.class_name || "").toLowerCase().includes(query) ||
                (item.lane || "").toLowerCase().includes(query)
            );
        });

        if (filtered.length === 0) {
            detectionsTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No matching active detections</td></tr>`;
            return;
        }

        let rows = "";
        filtered.slice(0, 15).forEach((item) => {
            const bboxStr = item.bbox ? `[${item.bbox.join(', ')}]` : '-';
            const speedStr = item.speed_kmh ? `${item.speed_kmh} km/h` : '0 km/h';

            rows += `
                <tr>
                    <td>${item.timestamp || '-'}</td>
                    <td><strong>#${item.track_id}</strong></td>
                    <td><span class="badge badge-ai">${item.class_name}</span></td>
                    <td>${item.confidence || '-'}</td>
                    <td>${item.lane || 'Outside'}</td>
                    <td>${speedStr}</td>
                    <td>${item.direction || 'Stationary'}</td>
                    <td><code>${bboxStr}</code></td>
                </tr>
            `;
        });

        detectionsTableBody.innerHTML = rows;
    }

    // ==========================================
    // 3. Real-Time Charts (Chart.js)
    // ==========================================
    function initCharts() {
        // Density Trend Line Chart
        const ctxDensity = document.getElementById("densityChart").getContext("2d");
        densityChart = new Chart(ctxDensity, {
            type: "line",
            data: {
                labels: Array(maxChartPoints).fill(""),
                datasets: [
                    {
                        label: "Traffic Density Index (%)",
                        data: Array(maxChartPoints).fill(0),
                        borderColor: "#06b6d4",
                        backgroundColor: "rgba(6, 182, 212, 0.12)",
                        borderWidth: 2,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0
                    },
                    {
                        label: "Active Vehicles",
                        data: Array(maxChartPoints).fill(0),
                        borderColor: "#10b981",
                        borderWidth: 2,
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: "#94a3b8", font: { size: 11 } }
                    }
                },
                scales: {
                    x: { display: false },
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#64748b", font: { size: 10 } }
                    }
                }
            }
        });

        // Vehicle Distribution Doughnut Chart
        const ctxClass = document.getElementById("classDistChart").getContext("2d");
        classDistChart = new Chart(ctxClass, {
            type: "doughnut",
            data: {
                labels: ["Cars", "Bikes", "Buses", "Trucks", "Bicycles", "Persons"],
                datasets: [{
                    data: [1, 0, 0, 0, 0, 0],
                    backgroundColor: [
                        "#06b6d4",
                        "#8b5cf6",
                        "#f59e0b",
                        "#10b981",
                        "#eab308",
                        "#94a3b8"
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: "#94a3b8", font: { size: 10 }, boxWidth: 12 }
                    }
                },
                cutout: "68%"
            }
        });
    }

    function updateCharts(data) {
        if (!densityChart || !classDistChart) return;

        // Update Line Chart
        const densityScore = data.overall_metrics?.overall_density_score || 0;
        const activeCount = data.total_active_vehicles || 0;

        densityChart.data.datasets[0].data.shift();
        densityChart.data.datasets[0].data.push(densityScore);

        densityChart.data.datasets[1].data.shift();
        densityChart.data.datasets[1].data.push(activeCount * 10); // scale for visibility

        densityChart.update("none");

        // Update Doughnut Chart
        const dist = data.class_distribution || {};
        classDistChart.data.datasets[0].data = [
            dist.car || 0,
            dist.motorcycle || 0,
            dist.bus || 0,
            dist.truck || 0,
            dist.bicycle || 0,
            dist.person || 0
        ];
        classDistChart.update("none");
    }

    // ==========================================
    // 4. Source Selection & Controls
    // ==========================================
    async function loadSourcesCatalog() {
        try {
            const res = await fetch("/api/sources");
            const data = await res.json();

            let optionsHtml = "";

            // Cameras
            if (data.cameras && data.cameras.length > 0) {
                optionsHtml += `<optgroup label="Physical Cameras / Webcams">`;
                data.cameras.forEach(c => {
                    optionsHtml += `<option value="${c.id}">${c.name}</option>`;
                });
                optionsHtml += `</optgroup>`;
            } else {
                optionsHtml += `<optgroup label="Physical Cameras"><option disabled>No physical webcam detected</option></optgroup>`;
            }

            // Samples
            if (data.samples && data.samples.length > 0) {
                optionsHtml += `<optgroup label="Sample Traffic Feeds">`;
                data.samples.forEach(s => {
                    optionsHtml += `<option value="${s.id}">${s.name}</option>`;
                });
                optionsHtml += `</optgroup>`;
            }

            // Uploads
            if (data.uploads && data.uploads.length > 0) {
                optionsHtml += `<optgroup label="User Uploaded Videos">`;
                data.uploads.forEach(u => {
                    optionsHtml += `<option value="${u.id}">${u.name}</option>`;
                });
                optionsHtml += `</optgroup>`;
            }

            selectVideoSource.innerHTML = optionsHtml;

            // Set selected value to match active
            const current = data.current_source;
            if (current) {
                selectVideoSource.value = `${current.type}:${current.value}`;
                tagCurrentSource.textContent = `${current.type.toUpperCase()}: ${current.value}`;
                document.getElementById("tag-res").textContent = current.resolution || "1280x720";
            }
        } catch (err) {
            console.error("Failed to load sources:", err);
        }
    }

    selectVideoSource.addEventListener("change", async (e) => {
        const val = e.target.value;
        const [type, ...rest] = val.split(":");
        const sourceVal = rest.join(":");

        const formData = new FormData();
        formData.append("source_type", type);
        formData.append("source_val", sourceVal);

        try {
            const res = await fetch("/api/set-source", {
                method: "POST",
                body: formData
            });
            const result = await res.json();
            if (result.status === "success") {
                tagCurrentSource.textContent = `${type.toUpperCase()}: ${sourceVal}`;
                // Reload image stream
                document.getElementById("live-stream-img").src = `/video_feed?t=${Date.now()}`;
            }
        } catch (err) {
            alert("Failed to switch video source: " + err.message);
        }
    });

    document.getElementById("btn-refresh-sources").addEventListener("click", loadSourcesCatalog);

    // Preset Selector
    selectLanePreset.addEventListener("change", async (e) => {
        const preset = e.target.value;
        const formData = new FormData();
        formData.append("preset_name", preset);

        try {
            await fetch("/api/lanes/preset", {
                method: "POST",
                body: formData
            });
        } catch (err) {
            console.error("Preset switch failed:", err);
        }
    });

    // Upload Video Handler
    inputVideoUpload.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        uploadStatus.textContent = "Uploading video...";
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/upload-video", {
                method: "POST",
                body: formData
            });
            const result = await res.json();
            if (result.status === "success") {
                uploadStatus.textContent = "Upload complete! Active now.";
                await loadSourcesCatalog();
                document.getElementById("live-stream-img").src = `/video_feed?t=${Date.now()}`;
                setTimeout(() => uploadStatus.textContent = "", 4000);
            }
        } catch (err) {
            uploadStatus.textContent = "Upload failed!";
            alert("Upload Error: " + err.message);
        }
    });

    // YOLO Confidence Slider
    sliderConfidence.addEventListener("input", (e) => {
        const conf = e.target.value;
        labelConfVal.textContent = `${conf}%`;
    });

    sliderConfidence.addEventListener("change", async (e) => {
        const conf = e.target.value / 100.0;
        const formData = new FormData();
        formData.append("confidence", conf);
        await fetch("/api/set-confidence", {
            method: "POST",
            body: formData
        });
    });

    // Overlay Toggles
    document.querySelectorAll(".tool-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const key = btn.dataset.overlay;
            const formData = new FormData();
            formData.append("key", key);

            try {
                const res = await fetch("/api/toggle-overlay", {
                    method: "POST",
                    body: formData
                });
                const result = await res.json();
                if (result.new_state) {
                    btn.classList.add("active");
                } else {
                    btn.classList.remove("active");
                }
            } catch (err) {
                console.error("Toggle overlay failed:", err);
            }
        });
    });

    // Playback Pause / Play Button
    const btnPausePlay = document.getElementById("btn-pause-play");
    const iconPausePlay = document.getElementById("icon-pause-play");
    const textPausePlay = document.getElementById("text-pause-play");

    btnPausePlay.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/playback/toggle-pause", { method: "POST" });
            const result = await res.json();
            isPaused = result.is_paused;
            if (isPaused) {
                textPausePlay.textContent = "Resume";
                iconPausePlay.setAttribute("data-lucide", "play");
            } else {
                textPausePlay.textContent = "Pause";
                iconPausePlay.setAttribute("data-lucide", "pause");
            }
            if (window.lucide) window.lucide.createIcons();
        } catch (err) {
            console.error("Toggle pause error:", err);
        }
    });

    // Snapshot Button
    document.getElementById("btn-snapshot").addEventListener("click", () => {
        window.open("/api/snapshot", "_blank");
    });

    // Reset Counts Button
    document.getElementById("btn-reset-counts").addEventListener("click", async () => {
        if (confirm("Reset cumulative vehicle counts and track IDs?")) {
            await fetch("/api/lanes/reset-counts", { method: "POST" });
        }
    });

    // Export CSV / JSON Buttons
    document.getElementById("btn-export-csv").addEventListener("click", () => {
        window.open("/api/export-logs?format=csv", "_blank");
    });

    document.getElementById("btn-export-json").addEventListener("click", () => {
        window.open("/api/export-logs?format=json", "_blank");
    });

    // Table Search Filter
    tableSearchInput.addEventListener("input", () => {
        // Instant filter on keystroke
    });

    // ==========================================
    // Initialization
    // ==========================================
    initCharts();
    loadSourcesCatalog();
    connectWebSocket();
});
