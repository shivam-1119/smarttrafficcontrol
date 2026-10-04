/**
 * Interactive Road Area & Lane Width Canvas Editor
 * Allows admin to freely adjust road width, 4 corner boundaries, perspective,
 * and individual lane divider lines with real-time on-screen drag-and-drop & slider controls.
 */

class LaneCanvasEditor {
    constructor() {
        this.canvas = document.getElementById("lane-canvas-overlay");
        this.ctx = this.canvas.getContext("2d");
        this.videoImg = document.getElementById("live-stream-img");
        this.drawer = document.getElementById("lane-editor-drawer");
        
        this.isActive = false;
        this.roadConfig = {
            lane_count: 4,
            top_left_pct: 16.0,
            top_right_pct: 76.0,
            bottom_left_pct: 4.0,
            bottom_right_pct: 82.0,
            top_y_pct: 5.0,
            bottom_y_pct: 96.0,
            trigger_y_pct: 62.0,
            lane_width_weights: [25.0, 25.0, 25.0, 25.0]
        };
        
        this.lanesData = [];
        this.draggingElement = null; // { type: 'top_left'|'top_right'|'bot_left'|'bot_right'|'divider'|'trigger_y', dividerIdx: 0 }
        this.dragRadius = 11;
        this.debounceTimer = null;

        this.initDOMElements();
        this.initEvents();
    }

    initDOMElements() {
        // Road Bounds Sliders
        this.sliderBotLeft = document.getElementById("slider-bot-left");
        this.sliderBotRight = document.getElementById("slider-bot-right");
        this.sliderTopLeft = document.getElementById("slider-top-left");
        this.sliderTopRight = document.getElementById("slider-top-right");

        this.sliderRoadTop = document.getElementById("slider-road-top");
        this.sliderRoadBottom = document.getElementById("slider-road-bottom");
        this.sliderTriggerY = document.getElementById("slider-trigger-y");

        this.valBotLeft = document.getElementById("val-bot-left");
        this.valBotRight = document.getElementById("val-bot-right");
        this.valTopLeft = document.getElementById("val-top-left");
        this.valTopRight = document.getElementById("val-top-right");

        this.valRoadTop = document.getElementById("val-road-top");
        this.valRoadBottom = document.getElementById("val-road-bottom");
        this.valTriggerY = document.getElementById("val-trigger-y");
        this.labelRoadXSpan = document.getElementById("label-road-x-span");
        this.labelTopXSpan = document.getElementById("label-top-x-span");
        this.labelRoadYSpan = document.getElementById("label-road-y-span");
        this.labelLaneCount = document.getElementById("label-lane-count");

        this.laneWidthsSlidersContainer = document.getElementById("lane-widths-sliders-container");
    }

    initEvents() {
        window.addEventListener("resize", () => this.resizeCanvas());
        this.videoImg.addEventListener("load", () => this.resizeCanvas());

        // Canvas mouse interactions for direct on-screen dragging
        this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
        this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
        this.canvas.addEventListener("mouseup", () => this.onMouseUp());
        this.canvas.addEventListener("mouseleave", () => this.onMouseUp());

        // Open/Close buttons
        document.getElementById("btn-open-lane-editor")?.addEventListener("click", () => this.toggleEditor(true));
        document.getElementById("btn-toolbar-road-editor")?.addEventListener("click", () => this.toggleEditor(true));
        document.getElementById("btn-close-lane-editor")?.addEventListener("click", () => this.toggleEditor(false));
        document.getElementById("btn-save-custom-lanes")?.addEventListener("click", () => this.saveLanes(true));
        document.getElementById("btn-equalize-lanes")?.addEventListener("click", () => this.equalizeWidths());

        // Cover Left Traffic (Expand road to include cars, truck, bikes on left side)
        const applyCoverLeft = () => {
            this.roadConfig.bottom_left_pct = 4.0;
            this.roadConfig.top_left_pct = 16.0;
            this.roadConfig.bottom_right_pct = 82.0;
            this.roadConfig.top_right_pct = 76.0;
            this.roadConfig.top_y_pct = 5.0;
            this.roadConfig.bottom_y_pct = 96.0;
            this.updateUIFromConfig();
            this.triggerApply();
        };

        // Full Road Width (100% camera panorama)
        const applyFullRoad = () => {
            this.roadConfig.bottom_left_pct = 1.0;
            this.roadConfig.top_left_pct = 2.0;
            this.roadConfig.bottom_right_pct = 99.0;
            this.roadConfig.top_right_pct = 98.0;
            this.roadConfig.top_y_pct = 4.0;
            this.roadConfig.bottom_y_pct = 96.0;
            this.updateUIFromConfig();
            this.triggerApply();
        };

        document.getElementById("btn-auto-left-traffic")?.addEventListener("click", applyCoverLeft);
        document.getElementById("btn-strip-left-traffic")?.addEventListener("click", applyCoverLeft);
        document.getElementById("btn-full-road")?.addEventListener("click", applyFullRoad);
        document.getElementById("btn-strip-full-road")?.addEventListener("click", applyFullRoad);

        // Lane Count Switchers
        document.querySelectorAll("#lane-count-btn-group .btn-count").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const count = parseInt(btn.dataset.count);
                this.setLaneCount(count);
            });
        });

        // Sliders Listeners
        this.sliderBotLeft?.addEventListener("input", (e) => {
            this.roadConfig.bottom_left_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderBotRight?.addEventListener("input", (e) => {
            this.roadConfig.bottom_right_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderTopLeft?.addEventListener("input", (e) => {
            this.roadConfig.top_left_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderTopRight?.addEventListener("input", (e) => {
            this.roadConfig.top_right_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderRoadTop?.addEventListener("input", (e) => {
            this.roadConfig.top_y_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderRoadBottom?.addEventListener("input", (e) => {
            this.roadConfig.bottom_y_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        this.sliderTriggerY?.addEventListener("input", (e) => {
            this.roadConfig.trigger_y_pct = parseFloat(e.target.value);
            this.updateUIFromConfig();
            this.triggerApply();
        });

        // Quick alignment actions
        document.getElementById("btn-shift-left")?.addEventListener("click", () => this.shiftRoad(-4));
        document.getElementById("btn-shift-right")?.addEventListener("click", () => this.shiftRoad(4));
        document.getElementById("btn-expand-width")?.addEventListener("click", () => this.scaleRoadWidth(1.08));
        document.getElementById("btn-shrink-width")?.addEventListener("click", () => this.scaleRoadWidth(0.92));
    }

    resizeCanvas() {
        const rect = this.videoImg.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.canvas.style.width = `${rect.width}` + "px";
        this.canvas.style.height = `${rect.height}` + "px";
        if (this.isActive) this.render();
    }

    async toggleEditor(state) {
        this.isActive = (state !== undefined) ? state : !this.isActive;
        if (this.isActive) {
            this.drawer.classList.remove("hidden");
            this.canvas.style.pointerEvents = "auto";
            await this.loadLanes();
            this.resizeCanvas();
            if (window.lucide) window.lucide.createIcons();
        } else {
            this.drawer.classList.add("hidden");
            this.canvas.style.pointerEvents = "none";
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }

    async loadLanes() {
        try {
            const res = await fetch("/api/lanes");
            const data = await res.json();
            this.lanesData = data.lanes || [];
            if (data.road_config) {
                this.roadConfig = Object.assign(this.roadConfig, data.road_config);
            }
            this.updateUIFromConfig();
            this.render();
        } catch (err) {
            console.error("Failed to fetch lanes:", err);
        }
    }

    setLaneCount(count) {
        this.roadConfig.lane_count = count;
        this.roadConfig.lane_width_weights = Array(count).fill(100.0 / count);
        this.updateUIFromConfig();
        this.triggerApply();
    }

    equalizeWidths() {
        const count = this.roadConfig.lane_count;
        this.roadConfig.lane_width_weights = Array(count).fill(100.0 / count);
        this.updateUIFromConfig();
        this.triggerApply();
    }

    shiftRoad(deltaPct) {
        this.roadConfig.bottom_left_pct = Math.max(0, Math.min(95, this.roadConfig.bottom_left_pct + deltaPct));
        this.roadConfig.bottom_right_pct = Math.max(5, Math.min(100, this.roadConfig.bottom_right_pct + deltaPct));
        this.roadConfig.top_left_pct = Math.max(0, Math.min(95, this.roadConfig.top_left_pct + deltaPct));
        this.roadConfig.top_right_pct = Math.max(5, Math.min(100, this.roadConfig.top_right_pct + deltaPct));

        this.updateUIFromConfig();
        this.triggerApply();
    }

    scaleRoadWidth(scale) {
        const bCenter = (this.roadConfig.bottom_left_pct + this.roadConfig.bottom_right_pct) / 2.0;
        const bHalf = ((this.roadConfig.bottom_right_pct - this.roadConfig.bottom_left_pct) / 2.0) * scale;
        
        const tCenter = (this.roadConfig.top_left_pct + this.roadConfig.top_right_pct) / 2.0;
        const tHalf = ((this.roadConfig.top_right_pct - this.roadConfig.top_left_pct) / 2.0) * scale;

        this.roadConfig.bottom_left_pct = Math.max(0, Math.round(bCenter - bHalf));
        this.roadConfig.bottom_right_pct = Math.min(100, Math.round(bCenter + bHalf));
        this.roadConfig.top_left_pct = Math.max(0, Math.round(tCenter - tHalf));
        this.roadConfig.top_right_pct = Math.min(100, Math.round(tCenter + tHalf));

        this.updateUIFromConfig();
        this.triggerApply();
    }

    updateUIFromConfig() {
        // Update Count Buttons
        document.querySelectorAll("#lane-count-btn-group .btn-count").forEach(btn => {
            if (parseInt(btn.dataset.count) === this.roadConfig.lane_count) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        if (this.labelLaneCount) {
            this.labelLaneCount.textContent = `${this.roadConfig.lane_count} Lanes`;
        }

        // Update Slider inputs & value badges
        if (this.sliderBotLeft) this.sliderBotLeft.value = Math.round(this.roadConfig.bottom_left_pct);
        if (this.sliderBotRight) this.sliderBotRight.value = Math.round(this.roadConfig.bottom_right_pct);
        if (this.sliderTopLeft) this.sliderTopLeft.value = Math.round(this.roadConfig.top_left_pct);
        if (this.sliderTopRight) this.sliderTopRight.value = Math.round(this.roadConfig.top_right_pct);

        if (this.sliderRoadTop) this.sliderRoadTop.value = Math.round(this.roadConfig.top_y_pct);
        if (this.sliderRoadBottom) this.sliderRoadBottom.value = Math.round(this.roadConfig.bottom_y_pct);
        if (this.sliderTriggerY) this.sliderTriggerY.value = Math.round(this.roadConfig.trigger_y_pct);

        if (this.valBotLeft) this.valBotLeft.textContent = `${Math.round(this.roadConfig.bottom_left_pct)}%`;
        if (this.valBotRight) this.valBotRight.textContent = `${Math.round(this.roadConfig.bottom_right_pct)}%`;
        if (this.valTopLeft) this.valTopLeft.textContent = `${Math.round(this.roadConfig.top_left_pct)}%`;
        if (this.valTopRight) this.valTopRight.textContent = `${Math.round(this.roadConfig.top_right_pct)}%`;

        if (this.valRoadTop) this.valRoadTop.textContent = `${Math.round(this.roadConfig.top_y_pct)}%`;
        if (this.valRoadBottom) this.valRoadBottom.textContent = `${Math.round(this.roadConfig.bottom_y_pct)}%`;
        if (this.valTriggerY) this.valTriggerY.textContent = `${Math.round(this.roadConfig.trigger_y_pct)}%`;

        if (this.labelRoadXSpan) this.labelRoadXSpan.textContent = `${Math.round(this.roadConfig.bottom_left_pct)}% - ${Math.round(this.roadConfig.bottom_right_pct)}%`;
        if (this.labelTopXSpan) this.labelTopXSpan.textContent = `${Math.round(this.roadConfig.top_left_pct)}% - ${Math.round(this.roadConfig.top_right_pct)}%`;
        if (this.labelRoadYSpan) this.labelRoadYSpan.textContent = `${Math.round(this.roadConfig.top_y_pct)}% - ${Math.round(this.roadConfig.bottom_y_pct)}%`;

        // Render Individual Lane Width Sliders
        this.renderLaneWidthSliders();
    }

    renderLaneWidthSliders() {
        const weights = this.roadConfig.lane_width_weights || [];
        const total = weights.reduce((a, b) => a + b, 0) || 1;

        let html = "";
        weights.forEach((w, idx) => {
            const pct = Math.round((w / total) * 100);
            html += `
                <div class="lane-slider-item">
                    <div class="lane-slider-label">
                        <span>Lane ${idx + 1} Width:</span>
                        <strong id="val-lane-w-${idx}">${pct}%</strong>
                    </div>
                    <input type="range" class="slider-single-lane" data-idx="${idx}" min="5" max="80" value="${pct}" step="1">
                </div>
            `;
        });

        if (this.laneWidthsSlidersContainer) {
            this.laneWidthsSlidersContainer.innerHTML = html;

            document.querySelectorAll(".slider-single-lane").forEach(slider => {
                slider.addEventListener("input", (e) => {
                    const idx = parseInt(slider.dataset.idx);
                    const val = parseFloat(e.target.value);
                    this.roadConfig.lane_width_weights[idx] = val;
                    
                    const curTotal = this.roadConfig.lane_width_weights.reduce((a, b) => a + b, 0) || 1;
                    this.roadConfig.lane_width_weights.forEach((wt, i) => {
                        const p = Math.round((wt / curTotal) * 100);
                        const label = document.getElementById(`val-lane-w-${i}`);
                        if (label) label.textContent = `${p}%`;
                    });

                    this.triggerApply();
                });
            });
        }
    }

    triggerApply() {
        this.render();
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            this.saveLanes(false);
        }, 60);
    }

    async saveLanes(showAlert = false) {
        try {
            const res = await fetch("/api/lanes/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this.roadConfig)
            });
            const data = await res.json();
            if (data.status === "success" && data.summary) {
                this.lanesData = data.summary.lanes || [];
                this.render();
            }
            if (showAlert) {
                alert("Road area and lane widths applied successfully!");
                this.toggleEditor(false);
            }
        } catch (err) {
            console.error("Error saving lane configuration:", err);
            if (showAlert) alert("Failed to save: " + err.message);
        }
    }

    // ==========================================
    // Canvas Drag & Drop Interactions
    // ==========================================
    getCanvasCoordinates(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    onMouseDown(e) {
        if (!this.isActive) return;
        const mouse = this.getCanvasCoordinates(e);
        const cw = this.canvas.width;
        const ch = this.canvas.height;

        const topY = (this.roadConfig.top_y_pct / 100.0) * ch;
        const botY = (this.roadConfig.bottom_y_pct / 100.0) * ch;
        const trigY = (this.roadConfig.trigger_y_pct / 100.0) * ch;

        const topLX = (this.roadConfig.top_left_pct / 100.0) * cw;
        const topRX = (this.roadConfig.top_right_pct / 100.0) * cw;
        const botLX = (this.roadConfig.bottom_left_pct / 100.0) * cw;
        const botRX = (this.roadConfig.bottom_right_pct / 100.0) * cw;

        // 1. Check 4 Corner Pins
        if (Math.hypot(mouse.x - topLX, mouse.y - topY) < 22) {
            this.draggingElement = { type: 'top_left' };
            return;
        }
        if (Math.hypot(mouse.x - topRX, mouse.y - topY) < 22) {
            this.draggingElement = { type: 'top_right' };
            return;
        }
        if (Math.hypot(mouse.x - botLX, mouse.y - botY) < 22) {
            this.draggingElement = { type: 'bot_left' };
            return;
        }
        if (Math.hypot(mouse.x - botRX, mouse.y - botY) < 22) {
            this.draggingElement = { type: 'bot_right' };
            return;
        }

        // 2. Check Trigger Line
        if (Math.abs(mouse.y - trigY) < 14 && mouse.x >= Math.min(topLX, botLX) - 20 && mouse.x <= Math.max(topRX, botRX) + 20) {
            this.draggingElement = { type: 'trigger_y' };
            return;
        }

        // 3. Check Lane Divider Handles (Vertical orange lines)
        const weights = this.roadConfig.lane_width_weights || [];
        const totalW = weights.reduce((a, b) => a + b, 0) || 1;
        
        let cum = 0;
        for (let i = 0; i < weights.length - 1; i++) {
            cum += weights[i] / totalW;
            const tX = topLX + (topRX - topLX) * cum;
            const bX = botLX + (botRX - botLX) * cum;
            const midX = (tX + bX) / 2.0;
            const midY = (topY + botY) / 2.0;

            if (Math.hypot(mouse.x - midX, mouse.y - midY) < 22 || (Math.abs(mouse.x - midX) < 14 && mouse.y >= topY && mouse.y <= botY)) {
                this.draggingElement = { type: 'divider', dividerIdx: i };
                return;
            }
        }
    }

    onMouseMove(e) {
        if (!this.isActive) return;
        const mouse = this.getCanvasCoordinates(e);
        const cw = this.canvas.width;
        const ch = this.canvas.height;

        if (!this.draggingElement) {
            // Hover cursor styling
            const topY = (this.roadConfig.top_y_pct / 100.0) * ch;
            const botY = (this.roadConfig.bottom_y_pct / 100.0) * ch;
            const topLX = (this.roadConfig.top_left_pct / 100.0) * cw;
            const topRX = (this.roadConfig.top_right_pct / 100.0) * cw;
            const botLX = (this.roadConfig.bottom_left_pct / 100.0) * cw;
            const botRX = (this.roadConfig.bottom_right_pct / 100.0) * cw;

            const isNearCorner = [
                [topLX, topY], [topRX, topY], [botLX, botY], [botRX, botY]
            ].some(pt => Math.hypot(mouse.x - pt[0], mouse.y - pt[1]) < 18);

            if (isNearCorner) {
                this.canvas.style.cursor = "move";
            } else {
                this.canvas.style.cursor = "crosshair";
            }
            return;
        }

        const mouseXPct = (mouse.x / cw) * 100.0;
        const mouseYPct = (mouse.y / ch) * 100.0;

        if (this.draggingElement.type === 'top_left') {
            this.roadConfig.top_left_pct = Math.max(0, Math.min(this.roadConfig.top_right_pct - 5, mouseXPct));
            this.roadConfig.top_y_pct = Math.max(0, Math.min(this.roadConfig.bottom_y_pct - 10, mouseYPct));
            this.updateUIFromConfig();
            this.triggerApply();
        } else if (this.draggingElement.type === 'top_right') {
            this.roadConfig.top_right_pct = Math.min(100, Math.max(this.roadConfig.top_left_pct + 5, mouseXPct));
            this.roadConfig.top_y_pct = Math.max(0, Math.min(this.roadConfig.bottom_y_pct - 10, mouseYPct));
            this.updateUIFromConfig();
            this.triggerApply();
        } else if (this.draggingElement.type === 'bot_left') {
            this.roadConfig.bottom_left_pct = Math.max(0, Math.min(this.roadConfig.bottom_right_pct - 5, mouseXPct));
            this.roadConfig.bottom_y_pct = Math.min(100, Math.max(this.roadConfig.top_y_pct + 10, mouseYPct));
            this.updateUIFromConfig();
            this.triggerApply();
        } else if (this.draggingElement.type === 'bot_right') {
            this.roadConfig.bottom_right_pct = Math.min(100, Math.max(this.roadConfig.bottom_left_pct + 5, mouseXPct));
            this.roadConfig.bottom_y_pct = Math.min(100, Math.max(this.roadConfig.top_y_pct + 10, mouseYPct));
            this.updateUIFromConfig();
            this.triggerApply();
        } else if (this.draggingElement.type === 'trigger_y') {
            this.roadConfig.trigger_y_pct = Math.max(this.roadConfig.top_y_pct + 4, Math.min(this.roadConfig.bottom_y_pct - 4, mouseYPct));
            this.updateUIFromConfig();
            this.triggerApply();
        } else if (this.draggingElement.type === 'divider') {
            const dIdx = this.draggingElement.dividerIdx;
            const bLeft = this.roadConfig.bottom_left_pct;
            const bRight = this.roadConfig.bottom_right_pct;
            const roadSpan = bRight - bLeft;

            if (roadSpan > 5) {
                const relFraction = Math.max(0.02, Math.min(0.98, (mouseXPct - bLeft) / roadSpan));
                const weights = [...this.roadConfig.lane_width_weights];
                const totalW = weights.reduce((a, b) => a + b, 0);
                
                const prevCum = weights.slice(0, dIdx).reduce((a, b) => a + b, 0) / totalW;
                const nextCum = weights.slice(0, dIdx + 2).reduce((a, b) => a + b, 0) / totalW;
                
                if (relFraction > prevCum + 0.02 && relFraction < nextCum - 0.02) {
                    const combinedW = weights[dIdx] + weights[dIdx + 1];
                    const leftShare = (relFraction - prevCum) / (nextCum - prevCum);
                    weights[dIdx] = combinedW * leftShare;
                    weights[dIdx + 1] = combinedW * (1.0 - leftShare);
                    this.roadConfig.lane_width_weights = weights;
                    this.updateUIFromConfig();
                    this.triggerApply();
                }
            }
        }
    }

    onMouseUp() {
        this.draggingElement = null;
    }

    render() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        const cw = this.canvas.width;
        const ch = this.canvas.height;

        const weights = this.roadConfig.lane_width_weights || [];
        const totalW = weights.reduce((a, b) => a + b, 0) || 1;
        const laneCount = this.roadConfig.lane_count;

        const topY = (this.roadConfig.top_y_pct / 100.0) * ch;
        const botY = (this.roadConfig.bottom_y_pct / 100.0) * ch;
        const trigY = (this.roadConfig.trigger_y_pct / 100.0) * ch;

        const topLX = (this.roadConfig.top_left_pct / 100.0) * cw;
        const topRX = (this.roadConfig.top_right_pct / 100.0) * cw;
        const botLX = (this.roadConfig.bottom_left_pct / 100.0) * cw;
        const botRX = (this.roadConfig.bottom_right_pct / 100.0) * cw;

        let cumFractions = [0.0];
        let running = 0.0;
        weights.forEach(w => {
            running += w / totalW;
            cumFractions.push(running);
        });
        cumFractions[cumFractions.length - 1] = 1.0;

        // Draw each lane polygon & boundary
        for (let i = 0; i < laneCount; i++) {
            const f1 = cumFractions[i];
            const f2 = cumFractions[i + 1];

            const tl = topLX + (topRX - topLX) * f1;
            const tr = topLX + (topRX - topLX) * f2;
            const bl = botLX + (botRX - botLX) * f1;
            const br = botLX + (botRX - botLX) * f2;

            // Lane fill
            this.ctx.beginPath();
            this.ctx.moveTo(tl, topY);
            this.ctx.lineTo(tr, topY);
            this.ctx.lineTo(br, botY);
            this.ctx.lineTo(bl, botY);
            this.ctx.closePath();

            const isEven = i % 2 === 0;
            this.ctx.fillStyle = isEven ? "rgba(6, 182, 212, 0.22)" : "rgba(16, 185, 129, 0.22)";
            this.ctx.fill();

            this.ctx.lineWidth = 2;
            this.ctx.strokeStyle = isEven ? "#06b6d4" : "#10b981";
            this.ctx.stroke();

            // Lane Header Badge
            const midTopX = (tl + tr) / 2.0;
            this.ctx.fillStyle = "#090e1a";
            this.ctx.fillRect(midTopX - 34, topY + 6, 68, 20);
            this.ctx.strokeStyle = "#06b6d4";
            this.ctx.strokeRect(midTopX - 34, topY + 6, 68, 20);

            this.ctx.fillStyle = "#ffffff";
            this.ctx.font = "bold 11px Inter, sans-serif";
            this.ctx.textAlign = "center";
            this.ctx.fillText(`Lane ${i + 1}`, midTopX, topY + 20);

            // Draw Draggable Divider Handles
            if (i > 0) {
                this.ctx.beginPath();
                this.ctx.moveTo(tl, topY);
                this.ctx.lineTo(bl, botY);
                this.ctx.lineWidth = 3;
                this.ctx.strokeStyle = "#f59e0b";
                this.ctx.stroke();

                // Midpoint circle handle
                const midDivX = (tl + bl) / 2.0;
                const midDivY = (topY + botY) / 2.0;
                this.ctx.beginPath();
                this.ctx.arc(midDivX, midDivY, 10, 0, Math.PI * 2);
                this.ctx.fillStyle = "#f59e0b";
                this.ctx.fill();
                this.ctx.strokeStyle = "#ffffff";
                this.ctx.lineWidth = 2;
                this.ctx.stroke();
            }
        }

        // Draw Trigger / Counting Line
        this.ctx.beginPath();
        const trigLX = botLX + (topLX - botLX) * ((botY - trigY) / (botY - topY));
        const trigRX = botRX + (topRX - botRX) * ((botY - trigY) / (botY - topY));
        this.ctx.moveTo(trigLX, trigY);
        this.ctx.lineTo(trigRX, trigY);
        this.ctx.lineWidth = 3;
        this.ctx.strokeStyle = "#eab308";
        this.ctx.setLineDash([6, 6]);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Outer 4 corner anchor circles with glowing ring and label
        const corners = [
            { pt: [topLX, topY], label: "TL" },
            { pt: [topRX, topY], label: "TR" },
            { pt: [botLX, botY], label: "BL" },
            { pt: [botRX, botY], label: "BR" }
        ];

        corners.forEach(c => {
            const [cx, cy] = c.pt;
            // Outer glow
            this.ctx.beginPath();
            this.ctx.arc(cx, cy, this.dragRadius + 4, 0, Math.PI * 2);
            this.ctx.fillStyle = "rgba(6, 182, 212, 0.35)";
            this.ctx.fill();

            // Inner circle
            this.ctx.beginPath();
            this.ctx.arc(cx, cy, this.dragRadius, 0, Math.PI * 2);
            this.ctx.fillStyle = "#06b6d4";
            this.ctx.fill();
            this.ctx.strokeStyle = "#ffffff";
            this.ctx.lineWidth = 2.5;
            this.ctx.stroke();

            // Corner Label
            this.ctx.fillStyle = "#ffffff";
            this.ctx.font = "bold 9px Inter, sans-serif";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.fillText(c.label, cx, cy);
        });
    }
}

window.laneCanvasEditor = new LaneCanvasEditor();
