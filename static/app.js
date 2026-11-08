// Net Sentinel Frontend Controller
let telemetryLiveInterval = null;
let telemetryPaused = false;
let latestTelemetryData = null;
let localSimulationActive = false;
let localActiveScenario = null;
let stagedLogFile = null;

// Sequence counter: incremented on every fetch so stale responses are discarded.
let _telemetrySeq = 0;
// True while a fetch is in flight — prevents overlapping requests.
let _telemetryInFlight = false;
// Consecutive failure count for bounded backoff.
let _telemetryFailCount = 0;
const _TELEMETRY_BASE_MS = 2000;
const _TELEMETRY_MAX_BACKOFF_MS = 30000;

// Sanitize dynamic strings to prevent XSS injection
function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Pause polling when the tab is hidden; resume when visible again.
document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        _stopTelemetryInterval();
    } else if (!telemetryPaused) {
        _startTelemetryInterval();
        loadTelemetryGraph();
    }
});

// Prevent default drag and drop behavior across window
window.addEventListener("dragover", (e) => {
    e.preventDefault();
}, false);

window.addEventListener("drop", (e) => {
    e.preventDefault();
}, false);

// Wire all interactive event listeners after DOM is fully loaded
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initForms();
    initGlobalSearch();
    initModals();
    loadOverviewData();
    initTelemetryChart();
    initAudioSettings();

    // Mobile navigation drawer toggle wiring
    const hamburgerBtn = document.getElementById("hamburger-btn");
    const sidebar = document.getElementById("sidebar");
    const sidebarBackdrop = document.getElementById("sidebar-backdrop");

    function toggleMobileMenu() {
        if (sidebar && sidebarBackdrop) {
            sidebar.classList.toggle("mobile-open");
            sidebarBackdrop.classList.toggle("active");
        }
    }

    function closeMobileMenu() {
        if (sidebar && sidebarBackdrop) {
            sidebar.classList.remove("mobile-open");
            sidebarBackdrop.classList.remove("active");
        }
    }

    if (hamburgerBtn) hamburgerBtn.addEventListener("click", toggleMobileMenu);
    if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", closeMobileMenu);

    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            closeMobileMenu();
        });
    });

    const telemetryRangeEl = document.getElementById("telemetry-range");
    if (telemetryRangeEl) telemetryRangeEl.addEventListener("change", loadTelemetryGraph);

    const telemetryMetricEl = document.getElementById("telemetry-metric");
    if (telemetryMetricEl) telemetryMetricEl.addEventListener("change", () => {
        _telemetryMetricDirty = true;
        renderTelemetryChart();
    });

    const telemetryToggleBtn = document.getElementById("telemetry-toggle-btn");
    if (telemetryToggleBtn) telemetryToggleBtn.addEventListener("click", toggleTelemetryLive);

    const telemetryAttackBtn = document.getElementById("telemetry-attack-btn");
    if (telemetryAttackBtn) telemetryAttackBtn.addEventListener("click", triggerAttackSimulation);

    const telemetryResetBtn = document.getElementById("telemetry-reset-btn");
    if (telemetryResetBtn) telemetryResetBtn.addEventListener("click", resetAttackSimulation);

    document.querySelectorAll(".analytics-range-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const range = btn.getAttribute("data-range");
            if (range) setAnalyticsRange(range);
        });
    });

    const exportAnalyticsBtn = document.getElementById("export-analytics-btn");
    if (exportAnalyticsBtn) exportAnalyticsBtn.addEventListener("click", exportAnalyticsReport);

    const loadSampleCsvBtn = document.getElementById("load-sample-csv-btn");
    if (loadSampleCsvBtn) loadSampleCsvBtn.addEventListener("click", loadSampleCsv);

    const refreshHistoryBtn = document.getElementById("refresh-history-btn");
    if (refreshHistoryBtn) refreshHistoryBtn.addEventListener("click", loadAnalysisHistory);

    const refreshCollectorBtn = document.getElementById("refresh-collector-btn");
    if (refreshCollectorBtn) refreshCollectorBtn.addEventListener("click", loadLiveCollectorData);

    const refreshDevicesBtn = document.getElementById("refresh-devices-btn");
    if (refreshDevicesBtn) refreshDevicesBtn.addEventListener("click", loadDevices);

    const addDeviceModalBtn = document.getElementById("add-device-modal-btn");
    if (addDeviceModalBtn) addDeviceModalBtn.addEventListener("click", openNewDeviceModal);

    const refreshInvestigationsBtn = document.getElementById("refresh-investigations-btn");
    if (refreshInvestigationsBtn) refreshInvestigationsBtn.addEventListener("click", loadInvestigations);

    const addInvestigationModalBtn = document.getElementById("add-investigation-modal-btn");
    if (addInvestigationModalBtn) addInvestigationModalBtn.addEventListener("click", openNewInvestigationModal);

    const exportReportBtn = document.getElementById("export-report-btn");
    if (exportReportBtn) exportReportBtn.addEventListener("click", generateReport);

    const previewReportBtn = document.getElementById("preview-report-btn");
    if (previewReportBtn) previewReportBtn.addEventListener("click", toggleReportPreview);

    const closeInvestigationModalBtn = document.getElementById("close-investigation-modal-btn");
    if (closeInvestigationModalBtn) closeInvestigationModalBtn.addEventListener("click", closeModal);

    const cancelInvestigationModalBtn = document.getElementById("cancel-investigation-modal-btn");
    if (cancelInvestigationModalBtn) cancelInvestigationModalBtn.addEventListener("click", () => {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        closeModal();
    });

    const closeDeviceModalBtn = document.getElementById("close-device-modal-btn");
    if (closeDeviceModalBtn) closeDeviceModalBtn.addEventListener("click", closeDeviceModal);

    const cancelDeviceModalBtn = document.getElementById("cancel-device-modal-btn");
    if (cancelDeviceModalBtn) cancelDeviceModalBtn.addEventListener("click", () => {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        closeDeviceModal();
    });

    const newDeviceForm = document.getElementById("new-device-form");
    if (newDeviceForm) newDeviceForm.addEventListener("submit", handleCreateDevice);

    document.querySelectorAll("[data-action='switch-view']").forEach(el => {
        el.addEventListener("click", (e) => {
            e.preventDefault();
            const target = el.getAttribute("data-target");
            if (target) switchView(target);
        });
    });
});

// Initialize navigation with smooth transitions
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetId = item.getAttribute("data-target");
            switchView(targetId);
        });
    });
}

let _switchViewTimer = null;
let currentAnalyticsRange = "24H";

// View switching with coordinated fade and spring animation
function switchView(targetId) {
    if (window.NetSentinelSound) {
        window.NetSentinelSound.play("click");
    }

    if (_switchViewTimer) {
        clearTimeout(_switchViewTimer);
        _switchViewTimer = null;
    }

    const navItems = document.querySelectorAll(".nav-item");
    const viewPanels = document.querySelectorAll(".view-panel");

    // Fade out current views
    viewPanels.forEach(panel => {
        panel.style.opacity = "0";
        panel.style.transition = "opacity 0.2s ease";
    });

    // Switch active view panel
    _switchViewTimer = setTimeout(() => {
        navItems.forEach(nav => nav.classList.remove("active"));
        viewPanels.forEach(panel => {
            panel.classList.remove("active");
            panel.style.display = "none";
        });

        // Show and fade in new view
        const activeNav = document.querySelector(`.nav-item[data-target="${targetId}"]`);
        const activePanel = document.getElementById(targetId);

        if (activeNav) activeNav.classList.add("active");
        if (activePanel) {
            activePanel.classList.add("active");
            activePanel.style.display = "block";
            void activePanel.offsetWidth;
            activePanel.style.opacity = "1";
        }

        // Update page title
        const titleText = activeNav ? activeNav.textContent.trim() : "Net Sentinel";
        const titleEl = document.getElementById("current-page-title");
        if (titleEl) titleEl.textContent = titleText;

        // View-specific data loading when panel becomes active
        if (targetId === "overview-view") {
            _lastTime = performance.now();
            renderTelemetryChart();
        } else if (targetId === "analytics-view") {
            loadAnalyticsData(currentAnalyticsRange);
        } else if (targetId === "devices-view") {
            loadDevices();
        } else if (targetId === "network-view") {
            loadAnalysisHistory();
        } else if (targetId === "live-collector-view") {
            loadLiveCollectorData();
        } else if (targetId === "soc-alerts-view") {
            loadSocAlerts();
        } else if (targetId === "topology-view") {
            loadNetworkTopology();
        }
    }, 200);
}

async function loadLiveCollectorData() {
    try {
        const res = await fetch("/api/collector/status");
        if (!res.ok) throw new Error("Failed to load live collector status");
        const data = await res.json();
        
        const collector = data.collector || {};
        const badgeEl = document.getElementById("live-status-badge");
        const ifaceEl = document.getElementById("live-interface-name");
        const packetsEl = document.getElementById("live-packets-count");
        const bytesEl = document.getElementById("live-bytes-count");
        const tbody = document.getElementById("live-flows-tbody");

        if (badgeEl) {
            const isLive = collector.status === "LIVE";
            badgeEl.innerHTML = isLive 
                ? '<span class="badge badge-success"><i class="fa-solid fa-circle" style="font-size: 0.5rem; margin-right: 4px;"></i> LIVE</span>'
                : '<span class="badge badge-warning">DISCONNECTED</span>';
        }

        if (ifaceEl) ifaceEl.textContent = collector.interface || "None";
        if (packetsEl) packetsEl.textContent = (collector.packets_observed || 0).toLocaleString();
        if (bytesEl) {
            const kb = (collector.bytes_observed || 0) / 1024;
            bytesEl.textContent = kb > 1024 ? (kb / 1024).toFixed(2) + " MB" : kb.toFixed(1) + " KB";
        }

        if (tbody) {
            const flows = data.flows || [];
            if (flows.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 24px;">No live flows recorded. Start the collector agent to begin streaming.</td></tr>`;
            } else {
                tbody.innerHTML = flows.map(f => `
                    <tr>
                        <td>${escapeHtml(f.timestamp || "N/A")}</td>
                        <td><code>${escapeHtml(f.src_ip || "-")}</code></td>
                        <td><code>${escapeHtml(f.dst_ip || "-")}</code></td>
                        <td><code>${escapeHtml(f.src_port || "-")} → ${escapeHtml(f.dst_port || "-")}</code></td>
                        <td><span class="badge badge-info">${escapeHtml(f.protocol || "TCP")}</span></td>
                        <td>${escapeHtml(f.packets || 1)}</td>
                        <td>${escapeHtml(f.bytes || 0)} B</td>
                    </tr>
                `).join("");
            }
        }

        // Render Live Protocol Donut Visualization
        renderLiveProtocolDonut(data.protocols || []);
    } catch (err) {
        console.error("Failed to load live collector data", err);
    }
}

function _animateNumberCounter(element, targetNum, duration = 400) {
    if (!element) return;
    const currentText = (element.textContent || "").replace(/[^0-9.-]/g, "");
    const startNum = parseFloat(currentText) || 0;
    if (startNum === targetNum) return;
    const startTime = performance.now();
    function step(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(startNum + (targetNum - startNum) * ease);
        element.textContent = current.toLocaleString();
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            element.textContent = targetNum.toLocaleString();
        }
    }
    requestAnimationFrame(step);
}

function renderLiveProtocolDonut(protocols) {
    const donutSvg = document.getElementById("protocol-donut-chart");
    const legendList = document.getElementById("protocol-legend-list");
    const totalEl = document.getElementById("donut-total-flows");
    if (!donutSvg || !legendList) return;

    if (!protocols || protocols.length === 0) {
        if (totalEl) totalEl.textContent = "0";
        donutSvg.innerHTML = '<circle cx="50" cy="50" r="38" fill="transparent" stroke="#1e293b" stroke-width="12"></circle>';
        legendList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.82rem; font-style: italic;">No live flows captured yet.</span>';
        return;
    }

    const totalFlows = protocols.reduce((acc, p) => acc + (p.count || 0), 0);
    if (totalEl) _animateNumberCounter(totalEl, totalFlows);

    const colors = ["#B7F36B", "#82A8C8", "#75D69B", "#E9B65B", "#EF6B70"];
    const radius = 38;
    const circumference = 2 * Math.PI * radius; // ~238.76

    let accumulatedOffset = 0;
    const existingSlices = donutSvg.querySelectorAll(".protocol-donut-slice");
    const canReuseSlices = existingSlices.length === protocols.length;

    let circlesHtml = '<circle cx="50" cy="50" r="38" fill="transparent" stroke="#1e293b" stroke-width="12"></circle>';
    let legendHtml = '';

    protocols.forEach((p, idx) => {
        const count = p.count || 0;
        const pct = totalFlows > 0 ? (count / totalFlows) : 0;
        const dashLen = pct * circumference;
        const color = colors[idx % colors.length];

        if (canReuseSlices) {
            const sliceEl = existingSlices[idx];
            sliceEl.setAttribute("stroke", color);
            sliceEl.setAttribute("stroke-dasharray", `${dashLen} ${circumference}`);
            sliceEl.setAttribute("stroke-dashoffset", `${-accumulatedOffset}`);
            const titleEl = sliceEl.querySelector("title");
            if (titleEl) titleEl.textContent = `${p.protocol}: ${count} flows (${(pct * 100).toFixed(1)}%)`;
        } else {
            circlesHtml += `
                <circle class="protocol-donut-slice" cx="50" cy="50" r="38" fill="transparent"
                    stroke="${color}" stroke-width="12"
                    stroke-dasharray="${dashLen} ${circumference}"
                    stroke-dashoffset="${-accumulatedOffset}">
                    <title>${p.protocol}: ${count} flows (${(pct * 100).toFixed(1)}%)</title>
                </circle>
            `;
        }
        accumulatedOffset += dashLen;

        legendHtml += `
            <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem;">
                <span style="display: flex; align-items: center; gap: 6px;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background-color: ${color}; display: inline-block;"></span>
                    <strong style="color: #fff;">${escapeHtml(p.protocol)}</strong>
                </span>
                <span style="color: var(--text-secondary); font-family: 'JetBrains Mono', monospace;">${count} (${(pct * 100).toFixed(0)}%)</span>
            </div>
        `;
    });

    if (!canReuseSlices) {
        donutSvg.innerHTML = circlesHtml;
    }
    legendList.innerHTML = legendHtml;
}
async function loadOverviewData() {
    try {
        const res = await fetch("/api/overview");
        const data = await res.json();
        
        _animateNumberCounter(document.getElementById("stat-investigations"), data.investigations_count);
        _animateNumberCounter(document.getElementById("stat-devices"), data.devices_count);
        _animateNumberCounter(document.getElementById("stat-baselines"), data.integrity_baselines_count);
        _animateNumberCounter(document.getElementById("stat-alerts"), data.recent_investigations.length);

        const recentList = document.getElementById("recent-investigations-list");
        if (data.recent_investigations && data.recent_investigations.length > 0) {
            recentList.innerHTML = data.recent_investigations.map((inv, idx) => `
                <div class="timeline-row-anim" style="padding: 8px 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; animation-delay: ${idx * 35}ms;">
                    <div><strong>${escapeHtml(inv.id)}</strong>: ${escapeHtml(inv.title)}</div>
                    <span class="badge ${getInvestigationBadgeClass(inv.status)}">${escapeHtml(inv.status)}</span>
                </div>
            `).join("");
        } else {
            recentList.innerHTML = `<p style="color: var(--text-secondary); padding: 16px; font-style: italic;">No active investigations recorded.</p>`;
        }
    } catch (err) {
        console.error("Failed to load overview metrics", err);
        showNotification("Unable to load dashboard data", "error");
    }
}

// --- Telemetry Chart & Continuous Evolving Real-Time Motion Loop ---
let _telemetryAnimFrame = null;
let _telemetryMaxPoints = 48;
let _telemetryBuffer = [];
let _targetInbound = 20;
let _targetOutbound = 10;
let _currentDisplayMaxVal = 20;
let _scrollOffset = 0;
let _lastTime = performance.now();
let _phase = 0;
let _latestTelemetryPoint = null;
let _telemetryMetricDirty = false;
let _activeTelemetryMetric = "bandwidth";
let _telemetryLastUpdated = "";

function _metricPair(point, metric) {
    if (!point) return [0, 0];
    if (metric === "packets") return [point.packets_per_sec || 0, (point.packets_per_sec || 0) * 0.42];
    if (metric === "latency") return [point.latency_ms || 0, Math.max(0, (point.latency_ms || 0) * 0.55)];
    return [point.inbound_mbps || 0, point.outbound_mbps || 0];
}

function initTelemetrySeriesFromData(series, metric) {
    _telemetryBuffer = [];
    _scrollOffset = 0;
    const pts = series && series.length > 0 ? series : [];
    for (let i = 0; i < _telemetryMaxPoints; i++) {
        let inVal = 20, outVal = 10;
        if (pts.length > 0) {
            const srcIdx = Math.floor((i / _telemetryMaxPoints) * pts.length);
            const pair = _metricPair(pts[srcIdx], metric);
            inVal = pair[0];
            outVal = pair[1];
        }
        _telemetryBuffer.push({ inbound: inVal, outbound: outVal });
    }
    const lastPair = pts.length > 0 ? _metricPair(pts[pts.length - 1], metric) : [20, 10];
    _targetInbound = lastPair[0];
    _targetOutbound = lastPair[1];
    if (pts.length > 0) _latestTelemetryPoint = pts[pts.length - 1];
    const inValues = _telemetryBuffer.map(p => p.inbound);
    const outValues = _telemetryBuffer.map(p => p.outbound);
    const peak = Math.max(0, ...inValues, ...outValues);
    const floor = metric === "packets" ? 50 : metric === "latency" ? 5 : 8;
    _currentDisplayMaxVal = Math.max(peak * 1.18, floor);
}

function updateTelemetrySeriesWithLiveMeasurements(newInbound, newOutbound, point) {
    const inbound = Number.isFinite(newInbound) ? Math.max(0, newInbound) : 0;
    const outbound = Number.isFinite(newOutbound) ? Math.max(0, newOutbound) : 0;
    if (point) _latestTelemetryPoint = point;

    _targetInbound = inbound;
    _targetOutbound = outbound;
}

function _updateTelemetryHeader(metric) {
    const point = _latestTelemetryPoint;
    const pEl = document.getElementById("telemetry-stat-primary");
    const sEl = document.getElementById("telemetry-stat-secondary");
    if (!point || !pEl) return;
    const isLive = latestTelemetryData && latestTelemetryData.data_source === "REAL_COLLECTOR";
    const sourceLabel = isLive ? "Live Collector" : "Demo Simulation";

    if (metric === "packets") {
        pEl.textContent = `Rate: ${Math.round(point.packets_per_sec || 0)} pps`;
    } else if (metric === "latency") {
        pEl.textContent = `Latency: ${Number(point.latency_ms || 0).toFixed(1)} ms`;
    } else {
        pEl.textContent = `Throughput: ${Number(point.inbound_mbps || 0).toFixed(1)} Mbps`;
    }
    if (sEl) {
        const out = metric === "bandwidth"
            ? `Outbound: ${Number(point.outbound_mbps || 0).toFixed(1)} Mbps • ${sourceLabel}`
            : (metric === "latency" ? `Status: Stable • ${sourceLabel}` : `Source: ${sourceLabel}`);
        const suffix = _telemetryLastUpdated ? ` (${_telemetryLastUpdated} UTC)` : "";
        sEl.textContent = `${out}${suffix}`;
    }
}

function _drawSmoothWaveform(ctx, values, minVal, maxVal, height, stepX, shift) {
    if (!values || values.length < 2) return;
    const coords = values.map((val, idx) => ({
        x: idx * stepX - shift,
        y: height - ((val - minVal) / (maxVal - minVal)) * (height - 30) - 15
    }));
    ctx.moveTo(coords[0].x, coords[0].y);
    for (let i = 0; i < coords.length - 1; i++) {
        const p0 = coords[i];
        const p1 = coords[i + 1];
        const midX = (p0.x + p1.x) / 2;
        const midY = (p0.y + p1.y) / 2;
        ctx.quadraticCurveTo(p0.x, p0.y, midX, midY);
    }
    const last = coords[coords.length - 1];
    ctx.lineTo(last.x, last.y);
}

function renderTelemetryChart() {
    const canvas = document.getElementById("telemetry-canvas");
    if (!canvas) return;

    if (_telemetryAnimFrame) {
        cancelAnimationFrame(_telemetryAnimFrame);
        _telemetryAnimFrame = null;
    }

    if (telemetryPaused || document.hidden || canvas.offsetParent === null) {
        return;
    }

    const ctx = canvas.getContext("2d");
    const metricElem = document.getElementById("telemetry-metric");
    const metric = metricElem ? metricElem.value : "bandwidth";
    if (_telemetryMetricDirty || metric !== _activeTelemetryMetric) {
        _telemetryMetricDirty = false;
        _activeTelemetryMetric = metric;
        if (latestTelemetryData && latestTelemetryData.series) {
            initTelemetrySeriesFromData(latestTelemetryData.series, metric);
        } else {
            _telemetryBuffer = [];
        }
    }

    const containerWidth = canvas.parentElement ? canvas.parentElement.clientWidth : 600;
    const targetWidth = Math.max(containerWidth - 8, 200);
    const targetHeight = 180;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    if (canvas.width !== Math.floor(targetWidth * dpr) || canvas.height !== Math.floor(targetHeight * dpr)) {
        canvas.width = Math.floor(targetWidth * dpr);
        canvas.height = Math.floor(targetHeight * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const width = targetWidth;
    const height = targetHeight;
    const now = performance.now();
    const dt = Math.min((now - _lastTime) / 1000, 0.1);
    _lastTime = now;

    if (_telemetryBuffer.length === 0) {
        initTelemetrySeriesFromData(latestTelemetryData ? latestTelemetryData.series : [], metric);
    }

    if (!telemetryPaused) {
        _phase += dt * 2.5;
        const scrollSpeed = 0.5;
        _scrollOffset += dt * scrollSpeed;
        while (_scrollOffset >= 1.0) {
            _scrollOffset -= 1.0;
            if (_telemetryBuffer.length > 0) {
                _telemetryBuffer.shift();
                _telemetryBuffer.push({
                    inbound: _telemetryBuffer[_telemetryBuffer.length - 1].inbound,
                    outbound: _telemetryBuffer[_telemetryBuffer.length - 1].outbound
                });
            }
        }
    }

    const lastIdx = _telemetryBuffer.length - 1;
    if (lastIdx >= 0) {
        const lerpFactor = telemetryPaused ? 1.0 : Math.min(1.0 - Math.exp(-dt * 4.5), 0.35);
        _telemetryBuffer[lastIdx].inbound += (_targetInbound - _telemetryBuffer[lastIdx].inbound) * lerpFactor;
        _telemetryBuffer[lastIdx].outbound += (_targetOutbound - _telemetryBuffer[lastIdx].outbound) * lerpFactor;
    }

    _updateTelemetryHeader(metric);

    const inValues = _telemetryBuffer.map(p => p.inbound);
    const outValues = _telemetryBuffer.map(p => p.outbound);

    const peak = Math.max(0, ...inValues, ...outValues);
    const floor = metric === "packets" ? 50 : metric === "latency" ? 5 : 8;
    const targetMaxVal = Math.max(peak * 1.18, floor);
    _currentDisplayMaxVal += (targetMaxVal - _currentDisplayMaxVal) * (1 - Math.exp(-dt * 3.5));
    const maxVal = Math.max(_currentDisplayMaxVal, floor);
    const minVal = 0;

    ctx.clearRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(38, 53, 79, 0.45)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
        let y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    const span = Math.max(inValues.length - 1, 1);
    const stepX = width / span;
    const shift = telemetryPaused ? 0 : _scrollOffset * stepX;

    const inGrad = ctx.createLinearGradient(0, 0, 0, height);
    inGrad.addColorStop(0, "rgba(183, 243, 107, 0.22)");
    inGrad.addColorStop(1, "rgba(183, 243, 107, 0.0)");
    ctx.fillStyle = inGrad;
    ctx.beginPath();
    ctx.moveTo(0, height);
    _drawSmoothWaveform(ctx, inValues, minVal, maxVal, height, stepX, shift);
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#B7F36B";
    ctx.lineWidth = 2.0;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    _drawSmoothWaveform(ctx, inValues, minVal, maxVal, height, stepX, shift);
    ctx.stroke();

    const outGrad = ctx.createLinearGradient(0, 0, 0, height);
    outGrad.addColorStop(0, "rgba(130, 168, 200, 0.18)");
    outGrad.addColorStop(1, "rgba(130, 168, 200, 0.0)");
    ctx.fillStyle = outGrad;
    ctx.beginPath();
    ctx.moveTo(0, height);
    _drawSmoothWaveform(ctx, outValues, minVal, maxVal, height, stepX, shift);
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#82A8C8";
    ctx.lineWidth = 1.6;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    _drawSmoothWaveform(ctx, outValues, minVal, maxVal, height, stepX, shift);
    ctx.stroke();

    if (inValues.length > 0) {
        const lastIdx = inValues.length - 1;
        const lastX = lastIdx * stepX - shift;
        const lastInY = height - ((inValues[lastIdx] - minVal) / (maxVal - minVal)) * (height - 30) - 15;
        const lastOutY = height - ((outValues[lastIdx] - minVal) / (maxVal - minVal)) * (height - 30) - 15;

        const pulseScale = telemetryPaused ? 1 : (1 + Math.sin(_phase * 4.5) * 0.28);
        const pulseAlpha = telemetryPaused ? 0.35 : (0.35 + Math.sin(_phase * 4.5) * 0.15);

        ctx.fillStyle = `rgba(183, 243, 107, ${pulseAlpha * 0.45})`;
        ctx.beginPath();
        ctx.arc(lastX, lastInY, 9 * pulseScale, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(183, 243, 107, ${pulseAlpha})`;
        ctx.beginPath();
        ctx.arc(lastX, lastInY, 5.5 * pulseScale, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#B7F36B";
        ctx.beginPath();
        ctx.arc(lastX, lastInY, 3.0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(130, 168, 200, ${pulseAlpha * 0.45})`;
        ctx.beginPath();
        ctx.arc(lastX, lastOutY, 8 * pulseScale, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(130, 168, 200, ${pulseAlpha})`;
        ctx.beginPath();
        ctx.arc(lastX, lastOutY, 4.5 * pulseScale, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#82A8C8";
        ctx.beginPath();
        ctx.arc(lastX, lastOutY, 2.8, 0, Math.PI * 2);
        ctx.fill();
    }

    if (!telemetryPaused && !document.hidden) {
        _telemetryAnimFrame = requestAnimationFrame(renderTelemetryChart);
    }
}

// Generate local synthetic telemetry (robust fallback)
function generateLocalSyntheticTelemetry(range) {
    const points = range === "15m" ? 15 : range === "6h" ? 18 : range === "24h" ? 24 : 12;
    const series = [];
    const now = Math.floor(Date.now() / 1000);
    const step = range === "15m" ? 60 : range === "6h" ? 1200 : range === "24h" ? 3600 : 300;

    for (let i = 0; i < points; i++) {
        const ts = now - ((points - 1 - i) * step);
        const dt = new Date(ts * 1000);
        const dtStr = dt.toTimeString().split(" ")[0];
        
        let inbound = 25.0 + (Math.sin(i * 0.5) * 10.0);
        let outbound = 12.0 + (Math.cos(i * 0.5) * 5.0);
        let pps = 600 + Math.floor(Math.sin(i * 0.4) * 200);
        let latency = 18.0 + (Math.cos(i * 0.3) * 5.0);

        if (localSimulationActive && i >= points - 4) {
            if (localActiveScenario === "spike") {
                inbound *= 4.5;
                pps *= 3.2;
            } else if (localActiveScenario === "portscan") {
                pps *= 5.0;
                latency *= 2.8;
            } else if (localActiveScenario === "bruteforce") {
                latency *= 4.0;
                outbound *= 2.5;
            }
        }

        series.push({
            timestamp: dtStr,
            inbound_mbps: Number(inbound.toFixed(2)),
            outbound_mbps: Number(outbound.toFixed(2)),
            packets_per_sec: Math.floor(pps),
            latency_ms: Number(latency.toFixed(1))
        });
    }

    return {
        range: range,
        source: "DEMO DATA (Local Frontend Telemetry Fallback)",
        simulation_active: localSimulationActive,
        active_scenario: localActiveScenario,
        series: series
    };
}

// --- Telemetry polling helpers ---

function _stopTelemetryInterval() {
    if (telemetryLiveInterval !== null) {
        clearInterval(telemetryLiveInterval);
        telemetryLiveInterval = null;
    }
}

function _startTelemetryInterval() {
    _stopTelemetryInterval();
    const delay = _telemetryFailCount === 0
        ? _TELEMETRY_BASE_MS
        : Math.min(_TELEMETRY_BASE_MS * Math.pow(2, _telemetryFailCount), _TELEMETRY_MAX_BACKOFF_MS);
    telemetryLiveInterval = setInterval(loadTelemetryGraph, delay);
}

function _updateBanner(data) {
    const banner = document.getElementById("simulation-banner");
    if (!banner) return;
    if (data && data.simulation_active && data.active_scenario) {
        banner.style.display = "inline-block";
        banner.textContent = `DEMO — SIMULATED (${data.active_scenario.toUpperCase()})`;
    } else if (localSimulationActive && localActiveScenario) {
        banner.style.display = "inline-block";
        banner.textContent = `DEMO — LOCAL SIM (${localActiveScenario.toUpperCase()})`;
    } else {
        banner.style.display = "none";
    }
}

function _updateLastUpdated(ok) {
    if (ok) {
        const now = new Date();
        _telemetryLastUpdated = now.toTimeString().slice(0, 8);
    }
}

// Load telemetry graph. Discards stale responses via sequence counter.
// On failure, preserves the last valid chart and applies bounded backoff.
async function loadTelemetryGraph() {
    if (_telemetryInFlight) return;
    _telemetryInFlight = true;

    const rangeElem = document.getElementById("telemetry-range");
    const range = rangeElem ? rangeElem.value : "1h";
    updateTelemetryTimeAxis(range);
    const seq = ++_telemetrySeq;

    try {
        const res = await fetch(`/api/telemetry?range=${encodeURIComponent(range)}`);
        if (seq !== _telemetrySeq) return; // stale — a newer request superseded this one

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        let data;
        try {
            data = await res.json();
        } catch (_) {
            throw new Error("Malformed JSON response");
        }

        if (!data || !Array.isArray(data.series)) throw new Error("Missing series in response");

        // Validate numeric fields; drop any point with non-finite values.
        data.series = data.series.filter(s =>
            Number.isFinite(s.inbound_mbps) &&
            Number.isFinite(s.outbound_mbps) &&
            Number.isFinite(s.packets_per_sec) &&
            Number.isFinite(s.latency_ms)
        );

        latestTelemetryData = data;
        _telemetryFailCount = 0;
        _updateBanner(data);
        _updateLastUpdated(true);

        // Feed telemetry measurements into continuous streaming buffer
        if (data.series.length > 0) {
            const metricElem = document.getElementById("telemetry-metric");
            const metric = metricElem ? metricElem.value : "bandwidth";
            if (_currentDisplayInbound.length === 0) {
                initTelemetrySeriesFromData(data.series, metric);
            } else {
                const latestPoint = data.series[data.series.length - 1];
                const pair = _metricPair(latestPoint, metric);
                updateTelemetrySeriesWithLiveMeasurements(pair[0], pair[1], latestPoint);
            }
        }

        renderTelemetryChart();

        // Reset interval to base rate after recovery.
        if (!telemetryPaused && !document.hidden) _startTelemetryInterval();

    } catch (err) {
        if (seq !== _telemetrySeq) return;
        _telemetryFailCount = Math.min(_telemetryFailCount + 1, 5);
        // Preserve last valid chart — do not overwrite with synthetic fallback.
        const banner = document.getElementById("simulation-banner");
        if (banner && !latestTelemetryData) {
            banner.style.display = "inline-block";
            banner.textContent = `DEMO — API UNAVAILABLE (showing last known data)`;
        }
        if (!telemetryPaused && !document.hidden) _startTelemetryInterval();
    } finally {
        _telemetryInFlight = false;
    }
}

// Attack simulation — idempotent: repeated clicks update scenario, never stack state.
let _simInFlight = false;
async function triggerAttackSimulation() {
    if (_simInFlight) return;
    _simInFlight = true;

    const scenarioElem = document.getElementById("attack-scenario");
    const scenario = scenarioElem ? scenarioElem.value : "spike";

    localSimulationActive = true;
    localActiveScenario = scenario;

    const formData = new URLSearchParams();
    formData.append("scenario", scenario);

    const now = new Date().toISOString();
    const simulatedEvents = {
        spike: [{
            timestamp: now, severity: "warning", rule_id: "NET-RULE-SPIKE",
            src_ip: "192.0.2.50", dst_ip: "192.168.1.1",
            observed_label: "High Bandwidth Data Burst (850 Mbps) [SIMULATED]",
            recommended_action: "Inspect egress routes for data exfiltration."
        }],
        portscan: [{
            timestamp: now, severity: "danger", rule_id: "NET-RULE-PORT-SCAN",
            src_ip: "192.0.2.10", dst_ip: "192.168.1.50",
            observed_label: "Rapid SYN Scan across 512 ports [SIMULATED]",
            recommended_action: "Block source IP 192.0.2.10 at firewall perimeter."
        }],
        bruteforce: [{
            timestamp: now, severity: "danger", rule_id: "NET-RULE-BRUTEFORCE",
            src_ip: "192.0.2.88", dst_ip: "192.168.1.10",
            observed_label: "42 failed SSH authentication attempts in 30s [SIMULATED]",
            recommended_action: "Enforce SSH key-only authentication and rate limiting."
        }]
    }[scenario] || [];

    try {
        await fetch("/api/telemetry/simulate", { method: "POST", body: formData });
    } catch (_) {
        // Backend optional when offline; local state drives the chart.
    } finally {
        _simInFlight = false;
    }

    loadTelemetryGraph();
    loadNetworkResults({
        events: simulatedEvents,
        summary: { total: simulatedEvents.length, by_severity: { high: 1, medium: 0, low: 0 } }
    });
    if (window.NetSentinelSound) {
        window.NetSentinelSound.play("alert");
    }
}

// Reset attack simulation — clears demo state and the results table.
async function resetAttackSimulation() {
    if (window.NetSentinelSound) {
        window.NetSentinelSound.play("click");
    }
    localSimulationActive = false;
    localActiveScenario = null;

    const formData = new URLSearchParams();
    formData.append("scenario", "reset");

    try {
        await fetch("/api/telemetry/simulate", { method: "POST", body: formData });
    } catch (_) {}

    // Clear the network results table so simulated events don't persist.
    const container = document.getElementById("network-results-container");
    if (container) container.classList.add("hidden");

    loadTelemetryGraph();
}

// Toggle live telemetry polling. Guarantees exactly one interval is active.
function toggleTelemetryLive() {
    if (window.NetSentinelSound) {
        window.NetSentinelSound.play("click");
    }
    const btn = document.getElementById("telemetry-toggle-btn");
    if (telemetryPaused) {
        telemetryPaused = false;
        _startTelemetryInterval();
        loadTelemetryGraph();
        if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
    } else {
        telemetryPaused = true;
        _stopTelemetryInterval();
        if (btn) btn.innerHTML = '<i class="fa-solid fa-play"></i> Resume';
    }
}

// Initialize telemetry chart and start the single polling loop.
function initTelemetryChart() {
    const rangeElem = document.getElementById("telemetry-range");
    if (rangeElem) {
        rangeElem.addEventListener("change", (e) => {
            updateTelemetryTimeAxis(e.target.value);
        });
    }
    loadTelemetryGraph();
    _startTelemetryInterval();
    window.addEventListener("resize", renderTelemetryChart);
}

// --- Network Log Analysis ---
function renderLogFilePreview(file) {
    const selectedDisplay = document.getElementById("selected-file-display");
    if (!file || !selectedDisplay) return;
    selectedDisplay.style.display = "block";
    const sizeKb = (file.size / 1024).toFixed(1);
    selectedDisplay.innerHTML = `Selected: <strong>${escapeHtml(file.name)}</strong> (${sizeKb} KB)`;

    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target && e.target.result;
        if (typeof text === "string" && text.trim()) {
            const firstLine = text.trim().split("\n")[0].trim().replace(/^\ufeff/, "");
            if (firstLine) {
                const delim = (firstLine.includes(";") && !firstLine.includes(",")) ? ";" : (firstLine.includes("\t") && !firstLine.includes(",")) ? "\t" : ",";
                const cols = firstLine.split(delim).map(c => c.trim().toLowerCase().replace(/[-"'\s]/g, "_"));
                
                const hasTime = cols.some(c => ["timestamp", "time", "datetime", "date", "ts", "@timestamp"].includes(c));
                const hasSrc = cols.some(c => ["src_ip", "srcip", "source_ip", "sourceip", "source", "src", "src_addr", "source_address"].includes(c));
                const hasDst = cols.some(c => ["dst_ip", "dstip", "destination_ip", "destinationip", "dest_ip", "destip", "destination", "dest", "dst", "dst_addr", "destination_address"].includes(c));
                
                let statusBadge = "";
                if (hasTime && hasSrc && hasDst) {
                    statusBadge = `<span style="color: var(--accent-emerald); font-weight: 600;">✅ Required telemetry columns verified</span>`;
                } else {
                    const missing = [];
                    if (!hasTime) missing.push("timestamp");
                    if (!hasSrc) missing.push("src_ip");
                    if (!hasDst) missing.push("dst_ip");
                    statusBadge = `<span style="color: var(--accent-amber); font-weight: 500;">⚠️ Notice: Missing expected column(s): ${missing.join(", ")}</span>`;
                }
                selectedDisplay.innerHTML = `Selected: <strong>${escapeHtml(file.name)}</strong> (${sizeKb} KB)<br>${statusBadge}<br><span style="font-size: 0.75rem; color: var(--text-secondary); opacity: 0.9;">Header: ${escapeHtml(firstLine)}</span>`;
            }
        } else if (!text || !text.trim()) {
            selectedDisplay.innerHTML = `Selected: <strong>${escapeHtml(file.name)}</strong> (0 KB)<br><span style="color: var(--accent-rose);">⚠️ File is empty</span>`;
        }
    };
    reader.readAsText(file.slice(0, 4096));
}

async function loadSampleCsv() {
    try {
        const res = await fetch("/api/network/sample");
        if (!res.ok) throw new Error("Could not load sample CSV");
        const text = await res.text();
        const blob = new Blob([text], { type: "text/csv" });
        const file = new File([blob], "sample.csv", { type: "text/csv" });
        stagedLogFile = file;
        const logFileInput = document.getElementById("log-file-input");
        if (logFileInput) {
            try {
                const dt = new DataTransfer();
                dt.items.add(file);
                logFileInput.files = dt.files;
            } catch (_) {}
        }
        renderLogFilePreview(file);
        showNotification("Sample network log loaded. Click 'Analyze Traffic Logs' to run detection.", "success");
    } catch (err) {
        showNotification("Failed to load sample CSV: " + err.message, "error");
    }
}
window.loadSampleCsv = loadSampleCsv;

async function loadNetworkResults(data) {
    const container = document.getElementById("network-results-container");
    if (container) container.classList.remove("hidden");

    const summary = data?.summary || {};
    const recordsAnalyzed = summary?.total_records_analyzed ?? 0;
    const totalEvents = summary?.total ?? (data?.events ? data.events.length : 0);
    const highSev = summary?.by_severity?.high ?? 0;
    const mediumSev = summary?.by_severity?.medium ?? 0;
    const lowSev = summary?.by_severity?.low ?? 0;

    const pills = document.getElementById("network-summary-stats");
    if (pills) {
        pills.innerHTML = `
            <span class="badge badge-info">Analyzed: ${recordsAnalyzed} records</span>
            <span class="badge badge-info">Total Events: ${totalEvents}</span>
            <span class="badge badge-danger">High Severity: ${highSev}</span>
            <span class="badge badge-warning">Medium Severity: ${mediumSev}</span>
            <span class="badge badge-success">Low Severity: ${lowSev}</span>
        `;
    }

    // Render animated CSV threat distribution bars
    const threatChartWrap = document.getElementById("csv-threat-chart-wrap");
    const threatBarsContainer = document.getElementById("csv-threat-bars");
    if (threatChartWrap && threatBarsContainer) {
        threatChartWrap.style.display = "block";
        const maxSev = Math.max(highSev, mediumSev, lowSev, 1);
        const highH = Math.max(10, Math.round((highSev / maxSev) * 100));
        const medH = Math.max(10, Math.round((mediumSev / maxSev) * 100));
        const lowH = Math.max(10, Math.round((lowSev / maxSev) * 100));

        threatBarsContainer.innerHTML = `
            <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; justify-content: flex-end;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #EF6B70; font-family: 'JetBrains Mono', monospace; animation: badgePop 0.4s var(--ease-spring-bouncy) both;">${highSev}</span>
                <div class="mini-bar-anim" style="width: 100%; height: ${highH}%; background: linear-gradient(180deg, #EF6B70 0%, rgba(239, 107, 112, 0.4) 100%); border-radius: 4px; animation: barRise 0.5s var(--ease-spring-bouncy) both;"></div>
                <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">High</span>
            </div>
            <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; justify-content: flex-end;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #E9B65B; font-family: 'JetBrains Mono', monospace; animation: badgePop 0.4s var(--ease-spring-bouncy) 100ms both;">${mediumSev}</span>
                <div class="mini-bar-anim" style="width: 100%; height: ${medH}%; background: linear-gradient(180deg, #E9B65B 0%, rgba(233, 182, 91, 0.4) 100%); border-radius: 4px; animation: barRise 0.5s var(--ease-spring-bouncy) 100ms both;"></div>
                <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Medium</span>
            </div>
            <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; justify-content: flex-end;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #75D69B; font-family: 'JetBrains Mono', monospace; animation: badgePop 0.4s var(--ease-spring-bouncy) 200ms both;">${lowSev}</span>
                <div class="mini-bar-anim" style="width: 100%; height: ${lowH}%; background: linear-gradient(180deg, #75D69B 0%, rgba(117, 214, 155, 0.4) 100%); border-radius: 4px; animation: barRise 0.5s var(--ease-spring-bouncy) 200ms both;"></div>
                <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Low</span>
            </div>
        `;
    }

    const tbody = document.querySelector("#network-events-table tbody");
    if (tbody) {
        if (data && data.events && data.events.length > 0) {
            tbody.innerHTML = data.events.map((e, idx) => {
                const sev = (e.severity || "low").toLowerCase();
                const badgeClass = sev === "high" || sev === "danger" ? "badge-danger" : sev === "medium" || sev === "warning" ? "badge-warning" : "badge-success";
                return `
                    <tr class="timeline-row-anim" style="animation-delay: ${idx * 25}ms;">
                        <td>${escapeHtml(e.timestamp)}</td>
                        <td><span class="badge ${badgeClass}">${escapeHtml(e.severity || "low")}</span></td>
                        <td><code>${escapeHtml(e.rule_id)}</code></td>
                        <td><code>${escapeHtml(e.src_ip)}</code></td>
                        <td><code>${escapeHtml(e.dst_ip)}</code></td>
                        <td>${escapeHtml(e.observed_label)}</td>
                        <td>${escapeHtml(e.recommended_action)}</td>
                    </tr>
                `;
            }).join("");
        } else {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 20px;">
                        No suspicious events detected across ${escapeHtml(recordsAnalyzed || totalEvents || 0)} analyzed records.
                        All network traffic is within normal heuristic thresholds.
                    </td>
                </tr>
            `;
        }
    }
}

// Investigation management
function getInvestigationBadgeClass(status) {
    const s = String(status || "").toLowerCase().trim();
    if (s === "closed" || s === "resolved") return "badge-success";
    if (s === "in progress" || s === "review" || s === "in review" || s === "in_progress") return "badge-warning";
    if (s === "escalated" || s === "critical") return "badge-danger";
    return "badge-info";
}

function loadInvestigations() {
    return fetch("/api/investigations")
        .then(res => res.json())
        .then(investigations => {
            const tbody = document.querySelector("#investigations-table tbody");
            if (!tbody) return;

            if (investigations.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No investigation cases found.</td></tr>`;
                return;
            }

            tbody.innerHTML = investigations.map(inv => `
                <tr>
                    <td><code>${escapeHtml(inv.id)}</code></td>
                    <td><strong>${escapeHtml(inv.title)}</strong></td>
                    <td>${escapeHtml(inv.case_ref || "N/A")}</td>
                    <td><span class="badge ${getInvestigationBadgeClass(inv.status)}">${escapeHtml(inv.status)}</span></td>
                    <td>${escapeHtml(inv.created_at)}</td>
                </tr>
            `).join("");
        })
        .catch(err => {
            console.error("Failed to load investigations", err);
        });
}

// Form initialization
function initForms() {
    // 1. Network Analysis Form & Drag-and-Drop Handler
    const netForm = document.getElementById("network-upload-form");
    const dropZone = document.getElementById("network-drop-zone") || document.querySelector(".upload-drop-zone");
    const logFileInput = document.getElementById("log-file-input");

    if (dropZone && logFileInput) {
        dropZone.addEventListener("click", () => {
            logFileInput.click();
        });

        logFileInput.addEventListener("change", () => {
            if (logFileInput.files && logFileInput.files.length > 0) {
                stagedLogFile = logFileInput.files[0];
                renderLogFilePreview(stagedLogFile);
            }
        });

        dropZone.addEventListener("dragenter", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("dragover");
        });

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) {
                e.dataTransfer.dropEffect = "copy";
            }
            dropZone.classList.add("dragover");
        });

        dropZone.addEventListener("dragleave", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");

            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                const dropped = dt.files[0];
                stagedLogFile = dropped;
                try {
                    const container = new DataTransfer();
                    container.items.add(dropped);
                    logFileInput.files = container.files;
                } catch (_) {
                    // Staged file reference preserved for browsers lacking DataTransfer mutation
                }
                renderLogFilePreview(dropped);
            }
        });
    }

    if (netForm) {
        let _isAnalyzing = false;
        netForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (_isAnalyzing) {
                showNotification("Analysis already in progress. Please wait for results.", "error");
                return;
            }

            const file = (logFileInput && logFileInput.files && logFileInput.files[0]) || stagedLogFile;
            if (!file) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Please select or drop a CSV file to analyze.", "error");
                return;
            }

            // Ensure filename ends with .csv so backend accepts it
            const uploadName = file.name && file.name.toLowerCase().endsWith(".csv") ? file.name : `${file.name || "telemetry"}.csv`;
            const formData = new FormData();
            formData.append("file", file, uploadName);
            
            // Get and disable the submit button
            const analyzeBtn = netForm.querySelector('button[type="submit"]');
            const originalText = analyzeBtn ? (analyzeBtn.textContent || "Analyze Traffic Logs") : "Analyze Traffic Logs";
            _isAnalyzing = true;
            if (analyzeBtn) {
                analyzeBtn.setAttribute("disabled", "true");
                analyzeBtn.textContent = "Analyzing...";
            }

            try {
                // Send FormData directly without manually setting Content-Type (let browser set multipart boundary)
                const res = await fetch("/api/network/analyze", {
                    method: "POST",
                    body: formData
                });
                let data;
                try {
                    data = await res.json();
                } catch (_) {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                    showNotification("Server returned non-JSON response (status " + res.status + ")", "error");
                    return;
                }

                if (res.ok) {
                    loadNetworkResults(data);
                    loadAnalysisHistory();
                    const hasHighSeverity = data.events && data.events.some(ev => {
                        const s = String(ev.severity || "").toUpperCase();
                        return s === "HIGH" || s === "CRITICAL" || s === "DANGER";
                    });
                    if (window.NetSentinelSound) {
                        window.NetSentinelSound.play(hasHighSeverity ? "alert" : "success");
                    }
                    showNotification(`Analysis complete: ${data.events.length} suspicious events detected out of ${data.summary && data.summary.total_records_analyzed ? data.summary.total_records_analyzed : data.events.length} records.`, data.events.length > 0 ? "warning" : "success");
                    const container = document.getElementById("network-results-container");
                    if (container) container.scrollIntoView({ behavior: "smooth", block: "nearest" });
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                    let errorMsg = "Analysis failed";
                    if (data && data.detail) {
                        if (typeof data.detail === "string") {
                            errorMsg = data.detail;
                        } else if (Array.isArray(data.detail)) {
                            errorMsg = data.detail.map(d => d.msg || d.detail || JSON.stringify(d)).join("; ");
                        } else if (typeof data.detail === "object") {
                            errorMsg = JSON.stringify(data.detail);
                        }
                    }

                    // Render clear error inside the results container as well as popup
                    const container = document.getElementById("network-results-container");
                    if (container) {
                        container.classList.remove("hidden");
                        const pills = document.getElementById("network-summary-stats");
                        if (pills) {
                            pills.innerHTML = `<span class="badge badge-danger"><i class="fa-solid fa-circle-exclamation"></i> Analysis Rejected (HTTP ${res.status})</span>`;
                        }
                        const tbody = document.querySelector("#network-events-table tbody");
                        if (tbody) {
                            tbody.innerHTML = `
                                <tr>
                                    <td colspan="7" style="text-align: center; color: var(--accent-rose); padding: 24px; font-weight: 500;">
                                        <i class="fa-solid fa-triangle-exclamation" style="font-size: 1.5rem; margin-bottom: 8px; display: block;"></i>
                                        <strong>Error:</strong> ${escapeHtml(errorMsg)}
                                    </td>
                                </tr>
                            `;
                        }
                    }
                    showNotification(errorMsg, "error");
                }
            } catch (err) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNetworkError();
            } finally {
                _isAnalyzing = false;
                if (analyzeBtn) {
                    analyzeBtn.removeAttribute("disabled");
                    analyzeBtn.textContent = originalText;
                }
            }
        });
    }

    // 2. Embed Form with safe local preview
    const embedForm = document.getElementById("embed-form");
    const embedImageInput = document.getElementById("embed-image");
    let currentEmbedPreviewUrl = null;

    if (embedImageInput) {
        embedImageInput.addEventListener("change", () => {
            if (currentEmbedPreviewUrl) {
                URL.revokeObjectURL(currentEmbedPreviewUrl);
                currentEmbedPreviewUrl = null;
            }
            if (embedImageInput.files && embedImageInput.files[0]) {
                const file = embedImageInput.files[0];
                currentEmbedPreviewUrl = URL.createObjectURL(file);
                let previewBox = document.getElementById("embed-preview-box");
                if (!previewBox) {
                    previewBox = document.createElement("div");
                    previewBox.id = "embed-preview-box";
                    previewBox.style.marginTop = "8px";
                    embedImageInput.parentNode.appendChild(previewBox);
                }
                previewBox.innerHTML = `
                    <img src="${currentEmbedPreviewUrl}" alt="Cover Image Preview" style="max-height: 100px; max-width: 100%; border-radius: 6px; border: 1px solid var(--border-color); object-fit: contain; margin-top: 6px;" />
                `;
            } else {
                const previewBox = document.getElementById("embed-preview-box");
                if (previewBox) previewBox.innerHTML = "";
            }
        });
    }

    if (embedForm) {
        embedForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = embedImageInput ? embedImageInput.files[0] : null;
            const secret = document.getElementById("embed-secret").value;
            if (!file) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Please select a cover PNG image.", "error");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);
            formData.append("secret", secret);

            try {
                const res = await fetch("/api/stego/embed", { method: "POST", body: formData });
                const data = await res.json();
                const box = document.getElementById("embed-result");
                box.classList.remove("hidden");
                if (res.ok) {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                    box.className = "result-box result-success";
                    const downloadHref = data.image_data || data.download_url;
                    const fileName = data.filename || "encoded_image.png";
                    box.innerHTML = `
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i>
                                <strong>${escapeHtml(data.message || "Payload embedded successfully.")}</strong>
                            </div>
                            <span class="badge badge-success"><i class="fa-solid fa-shield-halved"></i> Encoded</span>
                        </div>
                        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 8px;">
                            Carrier File: <span style="font-family: 'JetBrains Mono', monospace; color: var(--accent-sky);">${escapeHtml(fileName)}</span>
                        </div>
                        ${data.image_data ? `
                        <div style="margin: 8px 0;">
                            <img src="${data.image_data}" alt="Encoded Preview" style="max-height: 100px; max-width: 100%; display: block; border-radius: 6px; border: 1px solid var(--border-color); object-fit: contain;" />
                        </div>` : ''}
                        <a href="${downloadHref}" class="btn btn-primary" style="margin-top: 6px; display: inline-flex; align-items: center; gap: 6px;" download="${escapeHtml(fileName)}">
                            <i class="fa-solid fa-download"></i> Download Encoded PNG
                        </a>
                    `;
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                    box.className = "result-box result-danger";
                    const errorMsg = data && data.detail ? data.detail : "Embedding failed.";
                    box.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-circle-xmark" style="color: var(--accent-rose);"></i>
                            <div>
                                <strong>Embedding Error:</strong> ${escapeHtml(errorMsg)}
                            </div>
                        </div>
                    `;
                }
            } catch (err) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                const box = document.getElementById("embed-result");
                if (box) {
                    box.className = "result-box result-danger";
                    box.classList.remove("hidden");
                    box.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-circle-xmark" style="color: var(--accent-rose);"></i>
                            <div>
                                <strong>Error:</strong> Embedding request failed. Check server connection.
                            </div>
                        </div>
                    `;
                }
                showNotification("Embedding failed.", "error");
            }
        });
    }

    // 3. Extract Form with safe local preview
    const extractImageInput = document.getElementById("extract-image");
    let currentExtractPreviewUrl = null;

    if (extractImageInput) {
        extractImageInput.addEventListener("change", () => {
            if (currentExtractPreviewUrl) {
                URL.revokeObjectURL(currentExtractPreviewUrl);
                currentExtractPreviewUrl = null;
            }
            if (extractImageInput.files && extractImageInput.files[0]) {
                const file = extractImageInput.files[0];
                currentExtractPreviewUrl = URL.createObjectURL(file);
                let previewBox = document.getElementById("extract-preview-box");
                if (!previewBox) {
                    previewBox = document.createElement("div");
                    previewBox.id = "extract-preview-box";
                    previewBox.style.marginTop = "8px";
                    extractImageInput.parentNode.appendChild(previewBox);
                }
                previewBox.innerHTML = `
                    <img src="${currentExtractPreviewUrl}" alt="Carrier Image Preview" style="max-height: 100px; max-width: 100%; border-radius: 6px; border: 1px solid var(--border-color); object-fit: contain; margin-top: 6px;" />
                `;
            } else {
                const previewBox = document.getElementById("extract-preview-box");
                if (previewBox) previewBox.innerHTML = "";
            }
        });
    }

    const extractForm = document.getElementById("extract-form");
    if (extractForm) {
        extractForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("extract-image");
            const file = fileInput && fileInput.files ? fileInput.files[0] : null;
            if (!file) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Please select a file first.", "error");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/stego/extract", { method: "POST", body: formData });
                const data = await res.json();
                const box = document.getElementById("extract-result");
                box.classList.remove("hidden");
                if (res.ok) {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                    box.className = "result-box result-success";
                    box.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i>
                                <strong>Extracted Secret Payload</strong>
                                <span class="badge badge-success"><i class="fa-solid fa-check"></i> Decoded</span>
                            </div>
                            <button type="button" class="btn btn-secondary" id="copy-secret-btn" style="padding: 4px 10px; font-size: 0.78rem;">
                                <i class="fa-regular fa-copy"></i> Copy
                            </button>
                        </div>
                        <pre id="extracted-text-output"></pre>
                    `;
                    const textOutput = document.getElementById("extracted-text-output");
                    if (textOutput) {
                        textOutput.textContent = data.secret;
                    }
                    const copyBtn = document.getElementById("copy-secret-btn");
                    if (copyBtn) {
                        copyBtn.addEventListener("click", () => {
                            if (navigator.clipboard && navigator.clipboard.writeText) {
                                navigator.clipboard.writeText(data.secret).then(() => {
                                    copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                                    setTimeout(() => {
                                        copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                                    }, 2000);
                                    showNotification("Secret payload copied to clipboard.", "success");
                                }).catch(() => {
                                    showNotification("Failed to copy payload.", "error");
                                });
                            }
                        });
                    }
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                    box.className = "result-box result-danger";
                    const errorMsg = data && data.detail ? data.detail : "Extraction failed.";
                    box.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-circle-xmark" style="color: var(--accent-rose);"></i>
                            <div>
                                <strong>Extraction Error:</strong> ${escapeHtml(errorMsg)}
                            </div>
                        </div>
                        <pre id="extracted-text-output" style="display: none;"></pre>
                    `;
                }
            } catch (err) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                const box = document.getElementById("extract-result");
                if (box) {
                    box.className = "result-box result-danger";
                    box.classList.remove("hidden");
                    box.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-circle-xmark" style="color: var(--accent-rose);"></i>
                            <div>
                                <strong>Error:</strong> Extraction request failed. Check server connection.
                            </div>
                        </div>
                        <pre id="extracted-text-output" style="display: none;"></pre>
                    `;
                }
                showNotification("Extraction request failed.", "error");
            }
        });
    }

    // 4. Forensics Form with safe local preview via URL.createObjectURL
    const forensicsForm = document.getElementById("forensics-form");
    const forensicsFile = document.getElementById("forensics-file");
    let currentForensicsPreviewUrl = null;

    if (forensicsFile) {
        forensicsFile.addEventListener("change", () => {
            if (currentForensicsPreviewUrl) {
                URL.revokeObjectURL(currentForensicsPreviewUrl);
                currentForensicsPreviewUrl = null;
            }
            if (forensicsFile.files && forensicsFile.files[0]) {
                const file = forensicsFile.files[0];
                if (file.type.startsWith("image/")) {
                    currentForensicsPreviewUrl = URL.createObjectURL(file);
                    let previewBox = document.getElementById("forensics-preview-box");
                    if (!previewBox) {
                        previewBox = document.createElement("div");
                        previewBox.id = "forensics-preview-box";
                        previewBox.style.marginTop = "12px";
                        forensicsFile.parentNode.appendChild(previewBox);
                    }
                    previewBox.innerHTML = `
                        <div style="display: inline-flex; align-items: center; gap: 8px; background: var(--bg-surface-inset); border: 1px solid var(--border-default); border-radius: var(--radius-md); padding: 8px 12px; max-width: 100%;">
                            <span class="badge badge-info"><i class="fa-solid fa-image"></i> Preview</span>
                            <img src="${currentForensicsPreviewUrl}" alt="Local Forensics Preview" style="max-height: 120px; max-width: 100%; border-radius: 6px; border: 1px solid var(--border-subtle); object-fit: contain; background: #060a12;" />
                            <span style="font-size: 0.8rem; color: var(--text-secondary); margin-left: auto;">${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)</span>
                        </div>
                    `;
                }
            }
        });
    }

    if (forensicsForm) {
        forensicsForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = forensicsFile ? forensicsFile.files[0] : null;
            if (!file) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Please select an image file.", "error");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/forensics/analyze", { method: "POST", body: formData });
                const data = await res.json();
                if (res.ok) {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                }
                const container = document.getElementById("forensics-results");
                container.classList.remove("hidden");
                const details = document.getElementById("forensics-details");
                
                // Determine risk badge class based on susposity score
                const score = Number(data.susposity_score || 0);
                let riskBadgeClass = "badge-warning";
                let riskLabel = "Moderate Risk";
                if (score < 30) {
                    riskBadgeClass = "badge-success";
                    riskLabel = "Low Risk";
                } else if (score > 70) {
                    riskBadgeClass = "badge-danger";
                    riskLabel = "Elevated Risk";
                }

                details.innerHTML = `
                    <div class="forensics-stat-tile"><strong>Filename & Format</strong>${escapeHtml(data.filename)} &bull; ${escapeHtml(data.format)} (${escapeHtml(data.mode)})</div>
                    <div class="forensics-stat-tile"><strong>Resolution & Size</strong>${escapeHtml(data.dimensions)} &bull; ${escapeHtml(data.file_size_bytes)} bytes</div>
                    <div class="forensics-stat-tile"><strong>SHA-256 Hash</strong><code style="font-size: 0.82rem; word-break: break-all; background: #060a12; padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-subtle);">${escapeHtml(data.sha256)}</code></div>
                    <div class="forensics-stat-tile"><strong>LSB Susposity Score</strong><span class="badge ${riskBadgeClass}">${escapeHtml(data.susposity_score)} / 100 &bull; ${riskLabel}</span></div>
                    <div class="forensics-indicators-card"><strong>Heuristic Indicators</strong><ul class="forensics-indicator-list">${(data.indicators || []).map(i => `<li>${escapeHtml(i)}</li>`).join("")}</ul></div>
                `;
            } catch (err) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Forensics analysis failed.", "error");
            }
        });
    }

    // Integrity Form
    const integrityForm = document.getElementById("integrity-form");
    if (integrityForm) {
        integrityForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("integrity-file");
            const file = fileInput && fileInput.files ? fileInput.files[0] : null;
            if (!file) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Please select a file first.", "error");
                return;
            }
            const refHash = document.getElementById("integrity-ref").value;
            const formData = new FormData();
            formData.append("file", file);
            if (refHash) formData.append("reference_hash", refHash);

            try {
                const res = await fetch("/api/integrity/verify", { method: "POST", body: formData });
                const data = await res.json();
                if (res.ok) {
                    if (data.reference_hash) {
                        if (data.match) {
                            if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                        } else {
                            if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                        }
                    } else {
                        if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                    }
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                }
                const box = document.getElementById("integrity-result");
                box.classList.remove("hidden");

                let resultClass = "";
                let statusHtml = "";
                let statusIcon = "";
                let statusLabel = "";
                
                if (data.reference_hash) {
                    if (data.match) {
                        resultClass = "result-success";
                        statusIcon = '<i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i>';
                        statusLabel = "Hash MATCHES trusted reference";
                    } else {
                        resultClass = "result-danger";
                        statusIcon = '<i class="fa-solid fa-circle-xmark" style="color: var(--accent-rose);"></i>';
                        statusLabel = "Hash MISMATCH with reference";
                    }
                    statusHtml = `
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-default);">
                            ${statusIcon}
                            <span class="badge ${data.match ? "badge-success" : "badge-danger"}">${statusLabel}</span>
                        </div>
                    `;
                } else {
                    resultClass = "";
                    statusHtml = `
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-default);">
                            <i class="fa-solid fa-fingerprint" style="color: var(--accent-sky);"></i>
                            <span class="badge badge-info">Standalone hash computed (no reference provided)</span>
                        </div>
                    `;
                }
                
                box.className = `result-box ${resultClass}`.trim();

                box.innerHTML = `
                    <div style="margin-bottom: 8px;">
                        <strong>Filename:</strong> ${escapeHtml(data.filename)}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong>Computed SHA-256:</strong>
                        <code style="font-size: 0.82rem; word-break: break-all; background: #060a12; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border-subtle); display: block; margin-top: 4px; position: relative;">
                            ${escapeHtml(data.current_sha256)}
                            <button type="button" class="btn btn-secondary copy-hash-btn" data-hash="${escapeHtml(data.current_sha256)}" style="position: absolute; top: 6px; right: 6px; padding: 2px 8px; font-size: 0.7rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-default); border-radius: 4px; cursor: pointer;">
                                <i class="fa-regular fa-copy"></i>
                            </button>
                        </code>
                    </div>
                    ${data.reference_hash ? `<div style="margin-bottom: 8px;"><strong>Reference SHA-256:</strong> <code style="font-size: 0.82rem; word-break: break-all; color: var(--text-secondary);">${escapeHtml(data.reference_hash)}</code></div>` : ''}
                    ${statusHtml}
                `;

                if (!box._hasCopyListener) {
                    box._hasCopyListener = true;
                    box.addEventListener("click", (e) => {
                        const copyBtn = e.target.closest(".copy-hash-btn");
                        if (copyBtn) {
                            const hash = copyBtn.getAttribute("data-hash");
                            if (hash) {
                                navigator.clipboard.writeText(hash)
                                    .then(() => showNotification("SHA-256 hash copied to clipboard", "success"))
                                    .catch(() => showNotification("Failed to copy hash", "error"));
                            }
                        }
                    });
                }
            } catch (err) {
                showNotification("Integrity verification failed.", "error");
            }
        });
    }

    // New Investigation Modal Form
    const newInvForm = document.getElementById("new-investigation-form");
    if (newInvForm) {
        newInvForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const title = document.getElementById("inv-title").value;
            const description = document.getElementById("inv-desc").value;
            const case_ref = document.getElementById("inv-ref").value;

            const formData = new URLSearchParams();
            formData.append("title", title);
            formData.append("description", description);
            formData.append("case_ref", case_ref);

            try {
                const res = await fetch("/api/investigations", {
                    method: "POST",
                    body: formData
                });
                if (res.ok) {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("success");
                    closeModal();
                    loadInvestigations();
                    loadOverviewData();
                    showNotification("Investigation case created successfully", "success");
                } else {
                    if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                    showNotification("Failed to create investigation.", "error");
                }
            } catch (err) {
                if (window.NetSentinelSound) window.NetSentinelSound.play("error");
                showNotification("Request failed.", "error");
            }
        });
    }

    const copyReportBtn = document.getElementById("copy-report-json-btn");
    if (copyReportBtn) {
        copyReportBtn.addEventListener("click", async () => {
            const output = document.getElementById("report-json-output");
            let text = output ? output.textContent : "";
            if (!text || !text.trim()) {
                try {
                    const res = await fetch("/api/reports/export");
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    const data = await res.json();
                    text = JSON.stringify(data, null, 2);
                    if (output) output.textContent = text;
                } catch (err) {
                    showNotification("Failed to fetch report: " + err.message, "error");
                    return;
                }
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    copyReportBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                    setTimeout(() => {
                        copyReportBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy JSON';
                    }, 2000);
                    showNotification("Report JSON copied to clipboard", "success");
                }).catch(() => {
                    showNotification("Failed to copy JSON", "error");
                });
            }
        });
    }
}

const sileo = (function() {
    const DEFAULT_DURATION = 4000;
    const MAX_STACK = 5;

    const DEFAULT_ICONS = {
        success: 'fa-solid fa-circle-check',
        error: 'fa-solid fa-circle-xmark',
        warning: 'fa-solid fa-triangle-exclamation',
        info: 'fa-solid fa-circle-info'
    };

    function getToaster() {
        let toaster = document.getElementById('sileo-toaster');
        if (!toaster) {
            toaster = document.createElement('div');
            toaster.id = 'sileo-toaster';
            toaster.className = 'sileo-toaster';
            toaster.setAttribute('role', 'region');
            toaster.setAttribute('aria-label', 'Notifications');
            (document.body || document.documentElement).appendChild(toaster);
        }
        return toaster;
    }

    function dismissToast(toast) {
        if (!toast || toast.classList.contains('sileo-toast-leaving')) return;
        if (toast._sileoTimer) {
            clearTimeout(toast._sileoTimer);
            toast._sileoTimer = null;
        }
        toast.classList.add('sileo-toast-leaving');
        let cleaned = false;
        const cleanup = (e) => {
            if (e && (e.target !== toast || e.animationName !== 'sileo-exit')) return;
            if (cleaned) return;
            cleaned = true;
            toast.removeEventListener('animationend', cleanup);
            if (toast.parentNode) {
                toast.remove();
            }
        };
        toast.addEventListener('animationend', cleanup);
        setTimeout(cleanup, 320);
    }

    function show(options = {}) {
        const config = typeof options === 'string' ? { message: options } : (options || {});
        let type = String(config.type || 'info').toLowerCase();
        if (type === 'danger') type = 'error';
        if (type === 'warn') type = 'warning';
        if (!DEFAULT_ICONS[type]) type = 'info';

        const rawTitle = config.title ? String(config.title) : '';
        let rawDesc = config.description ? String(config.description) : '';
        if (!rawDesc && config.message) {
            rawDesc = String(config.message);
        }

        const duration = typeof config.duration === 'number' ? config.duration : DEFAULT_DURATION;
        const dismissible = config.dismissible !== false;
        const id = config.id || ('sileo-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8));

        const toaster = getToaster();
        const activeToasts = Array.from(toaster.querySelectorAll('.sileo-toast:not(.sileo-toast-leaving)'));
        if (activeToasts.length >= MAX_STACK) {
            const evictCount = activeToasts.length - MAX_STACK + 1;
            for (let i = 0; i < evictCount; i++) {
                dismissToast(activeToasts[i]);
            }
        }

        const toast = document.createElement('div');
        toast.id = id;
        toast.dataset.sileoId = id;
        toast.className = `sileo-toast sileo-toast-${type}`;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
        toast.setAttribute('aria-atomic', 'true');

        let iconMarkup = '';
        if (config.icon !== false) {
            const iconClass = config.icon || DEFAULT_ICONS[type] || DEFAULT_ICONS.info;
            iconMarkup = `<div class="sileo-icon"><i class="${escapeHtml(iconClass)}"></i></div>`;
        }

        let contentMarkup = '<div class="sileo-content">';
        if (rawTitle) {
            contentMarkup += `<div class="sileo-title">${escapeHtml(rawTitle)}</div>`;
        }
        if (rawDesc) {
            contentMarkup += `<div class="sileo-description">${escapeHtml(rawDesc)}</div>`;
        }
        contentMarkup += '</div>';

        let closeMarkup = '';
        if (dismissible) {
            closeMarkup = `<button type="button" class="sileo-close" aria-label="Close notification"><i class="fa-solid fa-xmark"></i></button>`;
        }

        let progressMarkup = '';
        if (duration > 0 && duration !== Infinity) {
            progressMarkup = `<div class="sileo-progress" style="animation-duration: ${duration}ms;"></div>`;
        }

        toast.innerHTML = `${iconMarkup}${contentMarkup}${closeMarkup}${progressMarkup}`;

        if (dismissible) {
            const closeBtn = toast.querySelector('.sileo-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    dismissToast(toast);
                });
            }
        }

        let remaining = duration;
        let startTimestamp = Date.now();
        let timer = null;

        const startTimer = () => {
            if (duration > 0 && duration !== Infinity) {
                startTimestamp = Date.now();
                timer = setTimeout(() => {
                    dismissToast(toast);
                }, remaining);
                toast._sileoTimer = timer;
            }
        };

        const pauseTimer = () => {
            if (timer) {
                clearTimeout(timer);
                timer = null;
                toast._sileoTimer = null;
                remaining -= Date.now() - startTimestamp;
                if (remaining < 50) remaining = 50;
            }
        };

        startTimer();

        toast.addEventListener('mouseenter', pauseTimer);
        toast.addEventListener('mouseleave', () => {
            if (!toast.classList.contains('sileo-toast-leaving')) {
                startTimer();
            }
        });

        toaster.appendChild(toast);
        return id;
    }

    function normalizeArgs(messageOrOpts, defaultType) {
        if (typeof messageOrOpts === 'string') {
            return { message: messageOrOpts, type: defaultType };
        }
        return { type: defaultType, ...messageOrOpts };
    }

    function dismiss(id) {
        if (!id) return;
        const toast = typeof id === 'string'
            ? document.getElementById(id) || document.querySelector(`[data-sileo-id="${id}"]`)
            : id;
        if (toast) {
            dismissToast(toast);
        }
    }

    function clear() {
        const toaster = document.getElementById('sileo-toaster');
        if (!toaster) return;
        const toasts = Array.from(toaster.querySelectorAll('.sileo-toast:not(.sileo-toast-leaving)'));
        toasts.forEach(dismissToast);
    }

    return {
        show,
        success(messageOrOpts) {
            return show(normalizeArgs(messageOrOpts, 'success'));
        },
        error(messageOrOpts) {
            return show(normalizeArgs(messageOrOpts, 'error'));
        },
        warning(messageOrOpts) {
            return show(normalizeArgs(messageOrOpts, 'warning'));
        },
        info(messageOrOpts) {
            return show(normalizeArgs(messageOrOpts, 'info'));
        },
        dismiss,
        clear
    };
})();

window.sileo = sileo;

function showNotification(message, type = "info", options = {}) {
    const opts = typeof options === 'object' && options !== null ? options : {};
    return sileo.show({ message, type, ...opts });
}

function showNetworkError() {
    showNotification('Network analysis request failed', 'error');
}

function updateTelemetryTimeAxis(range) {
    const axis = document.getElementById("telemetry-time-axis");
    if (!axis) return;
    const labelsByRange = {
        "15m": ["-15m", "-11m", "-7m", "-4m", "Live"],
        "1h": ["-60m", "-45m", "-30m", "-15m", "Live"],
        "6h": ["-6h", "-4.5h", "-3h", "-1.5h", "Live"],
        "24h": ["-24h", "-18h", "-12h", "-6h", "Live"]
    };
    const labels = labelsByRange[range] || labelsByRange["1h"];
    axis.innerHTML = labels.map(l => "<span>" + l + "</span>").join("");
}

async function loadDevices() {
    try {
        const res = await fetch("/api/devices");
        if (!res.ok) throw new Error("Failed to load devices");
        const devices = await res.json();
        const tbody = document.getElementById("devices-table-body");
        if (!tbody) return;

        if (!devices || devices.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 16px;">No devices registered. Click "Add Device" to record a host.</td></tr>`;
            return;
        }

        tbody.innerHTML = devices.map(dev => {
            const statusClass = dev.status === "Active" ? "badge-success" : dev.status === "Quarantined" ? "badge-danger" : "badge-warning";
            return `
                <tr>
                    <td><code>${escapeHtml(dev.id)}</code></td>
                    <td><code>${escapeHtml(dev.ip_address || "N/A")}</code></td>
                    <td><code>${escapeHtml(dev.mac_address || "N/A")}</code></td>
                    <td><span class="badge ${statusClass}">${escapeHtml(dev.status)}</span></td>
                    <td>${escapeHtml(dev.observation_source || "Unknown")}</td>
                    <td>${escapeHtml(dev.last_seen || "N/A")}</td>
                    <td><button type="button" class="btn btn-sm btn-outline-danger delete-device-btn" data-device-id="${escapeHtml(dev.id)}" title="Remove Device"><i class="fa-solid fa-trash"></i></button></td>
                </tr>
            `;
        }).join("");

        if (!tbody._hasDeleteListener) {
            tbody._hasDeleteListener = true;
            tbody.addEventListener("click", (e) => {
                const btn = e.target.closest(".delete-device-btn");
                if (btn) {
                    const id = btn.getAttribute("data-device-id");
                    if (id) deleteDevice(id);
                }
            });
        }
    } catch (err) {
        console.error("Failed to load devices", err);
        showNotification(err.message, "error");
    }
}

function openNewDeviceModal() {
    if (window.NetSentinelSound) window.NetSentinelSound.play("click");
    const modal = document.getElementById("device-modal");
    if (modal) modal.classList.remove("hidden");
}

function closeDeviceModal() {
    const modal = document.getElementById("device-modal");
    if (modal) modal.classList.add("hidden");
    const form = document.getElementById("new-device-form");
    if (form) form.reset();
}

async function handleCreateDevice(e) {
    e.preventDefault();
    const hostname = document.getElementById("dev-hostname").value;
    const ip = document.getElementById("dev-ip").value;
    const mac = document.getElementById("dev-mac").value;
    const status = document.getElementById("dev-status").value;
    const source = document.getElementById("dev-source").value;

    const formData = new FormData();
    formData.append("hostname", hostname);
    formData.append("ip_address", ip);
    formData.append("mac_address", mac);
    formData.append("status", status);
    formData.append("observation_source", source);

    try {
        const res = await fetch("/api/devices", { method: "POST", body: formData });
        let data = null;
        try { data = await res.json(); } catch (_) {}
        if (!res.ok) {
            const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "Failed to add device";
            throw new Error(detail);
        }
        if (window.NetSentinelSound) window.NetSentinelSound.play("success");
        showNotification("Device added successfully", "success");
        closeDeviceModal();
        loadDevices();
        loadOverviewData();
    } catch (err) {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        showNotification(err.message, "error");
    }
}

async function deleteDevice(deviceId) {
    if (!window.confirm("Are you sure you want to remove this device?")) return;
    try {
        const id = decodeURIComponent(deviceId);
        const res = await fetch(`/api/devices/${encodeURIComponent(id)}`, { method: "DELETE" });
        let data = null;
        try { data = await res.json(); } catch (_) {}
        if (!res.ok) {
            const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "Failed to remove device";
            throw new Error(detail);
        }
        if (window.NetSentinelSound) window.NetSentinelSound.play("success");
        showNotification("Device removed successfully", "success");
        loadDevices();
        loadOverviewData();
    } catch (err) {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        showNotification(err.message, "error");
    }
}

async function loadAnalysisHistory() {
    try {
        const res = await fetch("/api/network/history");
        if (!res.ok) throw new Error("Failed to load analysis history");
        const records = await res.json();
        const tbody = document.getElementById("analysis-history-tbody");
        if (!tbody) return;

        if (!records || records.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 16px;">No analysis history recorded yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = records.map(item => {
            const details = item.details && typeof item.details === "object" ? item.details : {};
            const recordsCount = details.total_records !== undefined ? details.total_records : "-";
            const threatCount = details.threat_count !== undefined ? details.threat_count : 0;
            const threatBadge = threatCount > 0
                ? `<span class="badge badge-danger">${escapeHtml(threatCount)} threats</span>`
                : `<span class="badge badge-success">0 threats</span>`;
            return `
                <tr>
                    <td>${escapeHtml(item.timestamp || "N/A")}</td>
                    <td><code>${escapeHtml(item.filename || "Unknown")}</code></td>
                    <td>${escapeHtml(item.operation_type || "Network Analysis")}</td>
                    <td>${escapeHtml(recordsCount)}</td>
                    <td>${threatBadge}</td>
                    <td><span class="badge badge-info">${escapeHtml(item.status || "Completed")}</span></td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed to load analysis history", err);
    }
}

function initGlobalSearch() {
    const searchInput = document.getElementById("global-search");
    const dropdown = document.getElementById("search-results-dropdown");
    if (!searchInput || !dropdown) return;

    let debounceTimer = null;
    let requestSeq = 0;

    function hideDropdown() {
        dropdown.classList.add("hidden");
    }

    window.openSearchResult = function(viewId) {
        hideDropdown();
        searchInput.value = "";
        switchView(viewId);
    };

    dropdown.addEventListener("click", (e) => {
        const item = e.target.closest(".search-result-item");
        if (item) {
            const vId = item.getAttribute("data-view-id");
            if (vId) {
                hideDropdown();
                searchInput.value = "";
                switchView(vId);
            }
        }
    });

    function renderSection(title, items, viewId, titleFn, subtitleFn) {
        if (!items || items.length === 0) return "";
        const header = `<div class="search-category-header">${escapeHtml(title)} (${items.length})</div>`;
        const rows = items.map(item => `
            <div class="search-result-item" data-view-id="${escapeHtml(viewId)}">
                <div class="search-title">${escapeHtml(titleFn(item))}</div>
                <div class="search-subtitle">${escapeHtml(subtitleFn(item))}</div>
            </div>
        `).join("");
        return header + rows;
    }

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim();
        if (debounceTimer) clearTimeout(debounceTimer);
        if (query.length < 2) {
            hideDropdown();
            return;
        }
        debounceTimer = setTimeout(async () => {
            const seq = ++requestSeq;
            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                if (seq !== requestSeq) return;
                if (!res.ok) throw new Error("Search failed");
                const data = await res.json();
                if (seq !== requestSeq) return;

                if (!data || data.total_results === 0) {
                    dropdown.innerHTML = `<div class="search-no-results">No matching records found for "${escapeHtml(query)}"</div>`;
                    dropdown.classList.remove("hidden");
                    return;
                }

                const results = data.results || {};
                dropdown.innerHTML = [
                    renderSection("Investigations", results.investigations, "investigations-view",
                        inv => inv.title || inv.id || "Investigation",
                        inv => [inv.id, inv.case_ref, inv.status].filter(Boolean).join(" • ")),
                    renderSection("Devices", results.devices, "devices-view",
                        dev => dev.hostname || dev.ip_address || dev.id || "Device",
                        dev => [dev.ip_address, dev.mac_address, dev.status].filter(Boolean).join(" • ")),
                    renderSection("Integrity Baselines", results.integrity_baselines, "integrity-view",
                        base => base.filename || "Baseline",
                        base => [base.sha256 ? base.sha256.slice(0, 16) + "..." : "", base.recorded_at].filter(Boolean).join(" • ")),
                    renderSection("Analysis History", results.analysis_history, "network-view",
                        item => item.filename || "Analysis",
                        item => [item.operation_type, item.timestamp, item.status].filter(Boolean).join(" • "))
                ].join("");
                dropdown.classList.remove("hidden");
            } catch (err) {
                if (seq !== requestSeq) return;
                dropdown.innerHTML = `<div class="search-no-results">${escapeHtml(err.message)}</div>`;
                dropdown.classList.remove("hidden");
            }
        }, 250);
    });

    document.addEventListener("click", (e) => {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            hideDropdown();
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        hideDropdown();
    });
}

function initModals() {
    const deviceModal = document.getElementById("device-modal");
    if (deviceModal) {
        deviceModal.addEventListener("click", (e) => {
            if (e.target === deviceModal) closeDeviceModal();
        });
    }

    const invModal = document.getElementById("investigation-modal");
    if (invModal) {
        invModal.addEventListener("click", (e) => {
            if (e.target === invModal) closeModal();
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal();
            closeDeviceModal();
        }
    });
}

function openNewInvestigationModal() {
    if (window.NetSentinelSound) window.NetSentinelSound.play("click");
    const modal = document.getElementById("investigation-modal");
    if (modal) modal.classList.remove("hidden");
}

function closeModal() {
    const modal = document.getElementById("investigation-modal");
    if (modal) modal.classList.add("hidden");
    const form = document.getElementById("new-investigation-form");
    if (form) form.reset();
}

async function toggleReportPreview() {
    const preview = document.getElementById("report-preview");
    if (!preview) return;

    if (!preview.classList.contains("hidden")) {
        preview.classList.add("hidden");
        return;
    }

    const output = document.getElementById("report-json-output");
    if (output && (!output.textContent || !output.textContent.trim())) {
        try {
            const res = await fetch("/api/reports/export");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            output.textContent = JSON.stringify(data, null, 2);
        } catch (err) {
            showNotification("Failed to load report preview: " + err.message, "error");
            return;
        }
    }
    preview.classList.remove("hidden");
}

async function generateReport() {
    try {
        const res = await fetch("/api/reports/export");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const preview = document.getElementById("report-preview");
        if (preview) {
            preview.classList.remove("hidden");
            const output = document.getElementById("report-json-output");
            if (output) output.textContent = JSON.stringify(data, null, 2);
        }

        const jsonBlob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const blobUrl = URL.createObjectURL(jsonBlob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `net_sentinel_report_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        if (window.NetSentinelSound) window.NetSentinelSound.play("success");
        showNotification("Investigation report exported successfully", "success");
    } catch (err) {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        showNotification("Failed to generate report.", "error");
    }
}

// ==========================================================================
// Network Security Analytics Controller (24H, 7D, 30D, 90D)
// ==========================================================================
let latestAnalyticsData = null;

async function setAnalyticsRange(range) {
    currentAnalyticsRange = range;
    
    // Update active button state
    document.querySelectorAll(".analytics-range-btn").forEach(btn => {
        if (btn.getAttribute("data-range") === range) {
            btn.className = "analytics-range-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-all bg-[#1c2944] text-white border border-[#38bdf8]/40 shadow-sm";
        } else {
            btn.className = "analytics-range-btn px-3 py-1.5 text-xs font-semibold rounded-md transition-all text-slate-400 hover:text-white";
        }
    });

    await loadAnalyticsData(range);
}

async function loadAnalyticsData(range = "24H") {
    try {
        const res = await fetch(`/api/analytics?range=${range}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        latestAnalyticsData = data;
        renderAnalyticsUI(data);
    } catch (err) {
        console.warn("Analytics API unavailable, generating local fallback dataset", err);
        const fallback = generateLocalAnalyticsData(range);
        latestAnalyticsData = fallback;
        renderAnalyticsUI(fallback);
    }
}

function renderAnalyticsUI(data) {
    // 1. Subtitle & Comparison line
    const subline = document.getElementById("analytics-subline");
    if (subline && data.comparison_subline) {
        subline.textContent = data.comparison_subline;
    }

    const m = data.metrics;
    if (!m) return;

    // 2. Metric 1: Throughput
    const m_tp_val = document.getElementById("m-tp-val");
    if (m_tp_val) _animateNumberCounter(m_tp_val, m.throughput.value);
    const m_tp_pill = document.getElementById("m-tp-pill");
    if (m_tp_pill) {
        const sign = m.throughput.change_pct >= 0 ? "+" : "";
        m_tp_pill.innerHTML = `<i class="fa-solid fa-arrow-trend-${m.throughput.change_pct >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.throughput.change_pct}%`;
        m_tp_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.throughput.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-tp-chart", m.throughput.bars, m.throughput.favorable ? "#B7F36B" : "#EF6B70");

    // 3. Metric 2: Threat Events
    const m_threat_val = document.getElementById("m-threat-val");
    if (m_threat_val) _animateNumberCounter(m_threat_val, m.threats.value);
    const m_threat_pill = document.getElementById("m-threat-pill");
    if (m_threat_pill) {
        const sign = m.threats.change_pct >= 0 ? "+" : "";
        m_threat_pill.innerHTML = `<i class="fa-solid fa-arrow-trend-${m.threats.change_pct >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.threats.change_pct}%`;
        m_threat_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.threats.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-threat-chart", m.threats.bars, m.threats.favorable ? "#82A8C8" : "#EF6B70");

    // 4. Metric 3: Active Hosts
    const m_hosts_val = document.getElementById("m-hosts-val");
    if (m_hosts_val) _animateNumberCounter(m_hosts_val, m.hosts.value);
    const m_hosts_pill = document.getElementById("m-hosts-pill");
    if (m_hosts_pill) {
        const sign = m.hosts.change_abs >= 0 ? "+" : "";
        m_hosts_pill.innerHTML = `<i class="fa-solid fa-arrow-${m.hosts.change_abs >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.hosts.change_abs} hosts`;
        m_hosts_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.hosts.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-hosts-chart", m.hosts.bars, "#82A8C8");

    // 5. Metric 4: Average Latency
    const m_lat_val = document.getElementById("m-lat-val");
    if (m_lat_val) _animateNumberCounter(m_lat_val, m.latency.value);
    const m_lat_pill = document.getElementById("m-lat-pill");
    if (m_lat_pill) {
        const sign = m.latency.change_diff >= 0 ? "+" : "";
        m_lat_pill.innerHTML = `<i class="fa-solid fa-arrow-${m.latency.change_diff <= 0 ? 'down' : 'up'} text-[9px]"></i> ${sign}${m.latency.change_diff} ms`;
        m_lat_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.latency.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-lat-chart", m.latency.bars, m.latency.favorable ? "#B7F36B" : "#E9B65B");

    // 6. Main Telemetry SVG Area Chart
    renderAnalyticsSvgChart(data.chart_series);
}

function renderMiniBars(containerId, values, barColor) {
    const el = document.getElementById(containerId);
    if (!el || !values || !values.length) return;
    const max = Math.max(...values, 1);
    const existingBars = el.querySelectorAll(".mini-bar-anim");
    if (existingBars.length === values.length) {
        // Reuse DOM and smoothly transition heights via CSS spring without redraw flicker
        values.forEach((v, idx) => {
            const hPct = Math.max(12, Math.round((v / max) * 100));
            existingBars[idx].style.height = `${hPct}%`;
            existingBars[idx].title = v;
            if (barColor) existingBars[idx].style.backgroundColor = barColor;
        });
        return;
    }
    // Initial mount: build DOM with staggered spring rise
    el.innerHTML = values.map((v, idx) => {
        const hPct = Math.max(12, Math.round((v / max) * 100));
        const delayMs = idx * 28;
        return `<span class="flex-1 rounded-sm opacity-85 hover:opacity-100 cursor-pointer mini-bar-anim" style="height: ${hPct}%; background-color: ${barColor}; animation: barRise 0.45s var(--ease-spring-bouncy) ${delayMs}ms both;" title="${v}"></span>`;
    }).join("");
}

function _buildSvgSmoothPath(pts) {
    if (!pts || pts.length === 0) return "";
    if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
        const midX = (pts[i].x + pts[i + 1].x) / 2;
        const midY = (pts[i].y + pts[i + 1].y) / 2;
        d += ` Q ${pts[i].x} ${pts[i].y}, ${midX} ${midY}`;
    }
    const last = pts[pts.length - 1];
    d += ` L ${last.x} ${last.y}`;
    return d;
}

function renderAnalyticsSvgChart(series) {
    const svg = document.getElementById("analytics-svg-chart");
    const axisLabels = document.getElementById("analytics-axis-labels");
    if (!svg || !series || !series.length) return;

    const maxIn = Math.max(...series.map(s => s.inbound_mbps), 10);
    const maxOut = Math.max(...series.map(s => s.outbound_mbps), 5);
    const maxVal = Math.max(maxIn, maxOut * 1.5, 20);

    const W = 1000;
    const H = 200;
    const n = series.length;
    const stepX = W / (n - 1);

    // Compute coordinates
    const inPoints = series.map((pt, i) => {
        const x = i * stepX;
        const y = H - (pt.inbound_mbps / maxVal) * (H - 30) - 15;
        return { x, y, pt };
    });

    const outPoints = series.map((pt, i) => {
        const x = i * stepX;
        const y = H - (pt.outbound_mbps / maxVal) * (H - 30) - 15;
        return { x, y, pt };
    });

    const inPath = _buildSvgSmoothPath(inPoints);
    const outPath = _buildSvgSmoothPath(outPoints);
    const inArea = `${inPath} L ${W} ${H} L 0 ${H} Z`;
    const outArea = `${outPath} L ${W} ${H} L 0 ${H} Z`;

    svg.innerHTML = `
        <defs>
            <linearGradient id="inboundGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#B7F36B" stop-opacity="0.22"/>
                <stop offset="100%" stop-color="#B7F36B" stop-opacity="0.0"/>
            </linearGradient>
            <linearGradient id="outboundGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#82A8C8" stop-opacity="0.18"/>
                <stop offset="100%" stop-color="#82A8C8" stop-opacity="0.0"/>
            </linearGradient>
        </defs>

        <!-- Subtle Grid Lines -->
        <line x1="0" y1="40" x2="${W}" y2="40" stroke="#252A32" stroke-dasharray="4 4" stroke-width="1"/>
        <line x1="0" y1="90" x2="${W}" y2="90" stroke="#252A32" stroke-dasharray="4 4" stroke-width="1"/>
        <line x1="0" y1="140" x2="${W}" y2="140" stroke="#252A32" stroke-dasharray="4 4" stroke-width="1"/>

        <!-- Inbound Area & Smooth Waveform with Motion Drawing Animations -->
        <path d="${inArea}" fill="url(#inboundGradient)" style="animation: chartAreaFade 0.65s var(--ease-spring-bouncy) forwards;" />
        <path d="${inPath}" fill="none" stroke="#B7F36B" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1500" stroke-dashoffset="1500" style="animation: chartLineDraw 0.85s var(--ease-spring-snappy) forwards;" />

        <!-- Outbound Area & Smooth Waveform with Staggered Motion Drawing Animations -->
        <path d="${outArea}" fill="url(#outboundGradient)" style="animation: chartAreaFade 0.65s var(--ease-spring-bouncy) 0.08s forwards;" />
        <path d="${outPath}" fill="none" stroke="#82A8C8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1500" stroke-dashoffset="1500" style="animation: chartLineDraw 0.85s var(--ease-spring-snappy) 0.08s forwards;" />

        <!-- Interactive Data Dots with Staggered Spring Pop -->
        ${inPoints.map((p, idx) => `<circle class="chart-dot-interactive" cx="${p.x}" cy="${p.y}" r="3.5" fill="#B7F36B" stroke="#090A0C" stroke-width="1.5" style="animation: dotPop 0.4s var(--ease-spring-bouncy) ${idx * 22}ms both;"><title>Inbound: ${p.pt.inbound_mbps} Mbps (${p.pt.timestamp})</title></circle>`).join("")}
        ${outPoints.map((p, idx) => `<circle class="chart-dot-interactive" cx="${p.x}" cy="${p.y}" r="3" fill="#82A8C8" stroke="#090A0C" stroke-width="1.5" style="animation: dotPop 0.4s var(--ease-spring-bouncy) ${idx * 22 + 80}ms both;"><title>Outbound: ${p.pt.outbound_mbps} Mbps (${p.pt.timestamp})</title></circle>`).join("")}
    `;

    // Axis labels
    if (axisLabels) {
        axisLabels.innerHTML = series.map((s, idx) => {
            // Show every 2nd or 3rd label on small screens
            return `<span>${s.timestamp}</span>`;
        }).filter((_, idx) => idx % 2 === 0 || idx === n - 1).join("");
    }
}

async function exportAnalyticsReport() {
    try {
        const res = await fetch(`/api/analytics/export?range=${encodeURIComponent(currentAnalyticsRange)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `net_sentinel_analytics_${currentAnalyticsRange.toLowerCase()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        showNotification("Analytics CSV exported successfully", "success");
    } catch (err) {
        console.error("Export download failed, falling back to direct navigation", err);
        window.location.href = `/api/analytics/export?range=${encodeURIComponent(currentAnalyticsRange)}`;
    }
}

function generateLocalAnalyticsData(range) {
    const sublines = {
        "24H": "Last 24 hours compared with the previous 24 hours.",
        "7D": "Last 7 days compared with the previous 7 days.",
        "30D": "Last 30 days compared with the previous 30 days.",
        "90D": "Last 90 days compared with the previous 90 days."
    };
    return {
        range: range,
        comparison_subline: sublines[range] || sublines["24H"],
        metrics: {
            throughput: { label: "Network Throughput", value: 34.2, change_pct: 5.2, favorable: true, bars: [12, 18, 22, 28, 32, 35, 41, 38, 30, 26, 31, 34] },
            threats: { label: "Threat Events", value: 14, change_pct: -8.4, favorable: true, bars: [3, 1, 4, 2, 0, 1, 2, 0, 1, 0, 1, 0] },
            hosts: { label: "Active Hosts", value: 48, change_abs: 4, favorable: true, bars: [35, 38, 40, 42, 45, 44, 46, 47, 45, 46, 48, 48] },
            latency: { label: "Average Latency", value: 18.4, change_diff: -1.2, favorable: true, bars: [22, 21, 20, 19, 19, 18, 19, 18, 18, 17, 18, 18] }
        },
        chart_series: [
            { timestamp: "00:00", inbound_mbps: 22.1, outbound_mbps: 10.4 },
            { timestamp: "04:00", inbound_mbps: 18.5, outbound_mbps: 8.2 },
            { timestamp: "08:00", inbound_mbps: 34.2, outbound_mbps: 15.6 },
            { timestamp: "12:00", inbound_mbps: 42.8, outbound_mbps: 21.0 },
            { timestamp: "16:00", inbound_mbps: 38.6, outbound_mbps: 18.2 },
            { timestamp: "20:00", inbound_mbps: 29.4, outbound_mbps: 13.5 }
        ]
    };
}

window.loadInvestigations = loadInvestigations;
window.openNewInvestigationModal = openNewInvestigationModal;
window.closeModal = closeModal;
window.openNewDeviceModal = openNewDeviceModal;
window.closeDeviceModal = closeDeviceModal;
window.handleCreateDevice = handleCreateDevice;
window.generateReport = generateReport;
window.toggleReportPreview = toggleReportPreview;
window.loadSocAlerts = loadSocAlerts;
window.loadNetworkTopology = loadNetworkTopology;

async function loadSocAlerts() {
    const tbody = document.getElementById("soc-alerts-tbody");
    if (!tbody) return;
    try {
        const res = await fetch("/api/soc/alerts");
        if (!res.ok) throw new Error("Failed to load security alerts");
        const alerts = await res.json();
        if (!alerts || alerts.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 20px;">No security alerts detected.</td></tr>`;
            return;
        }
        tbody.innerHTML = alerts.map((a, idx) => {
            const sev = (a.severity || "MEDIUM").toUpperCase();
            const badgeClass = sev === "CRITICAL" || sev === "HIGH" ? "badge-danger" : sev === "MEDIUM" ? "badge-warning" : "badge-success";
            return `
                <tr class="timeline-row-anim" style="animation-delay: ${idx * 25}ms;">
                    <td><code>${escapeHtml(a.alert_id)}</code></td>
                    <td><strong>${escapeHtml(a.title)}</strong></td>
                    <td><span class="badge ${badgeClass}">${sev}</span></td>
                    <td><code>${Math.round((a.confidence || 0.85) * 100)}%</code></td>
                    <td><code>${escapeHtml(a.source_ip || "N/A")}</code></td>
                    <td><span class="badge badge-info">${escapeHtml(a.status)}</span></td>
                    <td>
                        <button type="button" class="btn btn-sm btn-secondary triage-btn" data-alert-id="${escapeHtml(a.alert_id)}" data-status="ACKNOWLEDGED">Acknowledge</button>
                        <button type="button" class="btn btn-sm btn-primary triage-btn" data-alert-id="${escapeHtml(a.alert_id)}" data-status="RESOLVED">Resolve</button>
                    </td>
                </tr>
            `;
        }).join("");

        if (!tbody._hasTriageListener) {
            tbody._hasTriageListener = true;
            tbody.addEventListener("click", async (e) => {
                const btn = e.target.closest(".triage-btn");
                if (btn) {
                    const alertId = btn.getAttribute("data-alert-id");
                    const status = btn.getAttribute("data-status");
                    await triageSocAlert(alertId, status);
                }
            });
        }
    } catch (err) {
        console.error(err);
        showNotification("Failed to load SOC alerts", "error");
    }
}

async function triageSocAlert(alertId, status) {
    try {
        const res = await fetch(`/api/soc/alerts/${encodeURIComponent(alertId)}/triage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: status, analyst: "Lead-SOC-Analyst" })
        });
        if (!res.ok) throw new Error("Triage update failed");
        if (window.NetSentinelSound) window.NetSentinelSound.play("success");
        showNotification(`Alert ${alertId} marked as ${status}`, "success");
        loadSocAlerts();
    } catch (err) {
        if (window.NetSentinelSound) window.NetSentinelSound.play("error");
        showNotification("Failed to update alert status", "error");
    }
}

async function loadNetworkTopology() {
    const canvas = document.getElementById("topology-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    try {
        const res = await fetch("/api/intelligence/topology");
        if (!res.ok) throw new Error("Failed to load network topology");
        const data = await res.json();
        const nodes = data.nodes || [];
        const edges = data.edges || [];

        const width = canvas.parentElement.clientWidth || 600;
        const height = 400;
        canvas.width = width;
        canvas.height = height;

        ctx.clearRect(0, 0, width, height);

        // Draw grid
        ctx.strokeStyle = "rgba(38, 53, 79, 0.3)";
        ctx.lineWidth = 1;
        for (let x = 0; x < width; x += 40) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
        }
        for (let y = 0; y < height; y += 40) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
        }

        const nodePositions = {};
        nodes.forEach((node, idx) => {
            const angle = (idx / Math.max(nodes.length, 1)) * Math.PI * 2;
            const radius = Math.min(width, height) * 0.32;
            const x = width / 2 + Math.cos(angle) * radius;
            const y = height / 2 + Math.sin(angle) * radius;
            nodePositions[node.id] = { x, y, label: node.label };
        });

        edges.forEach(e => {
            const p1 = nodePositions[e.src_ip];
            const p2 = nodePositions[e.dst_ip];
            if (p1 && p2) {
                ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        });

        Object.values(nodePositions).forEach(pos => {
            ctx.fillStyle = "#B7F36B";
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 6, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = "#F1F3F5";
            ctx.font = "11px 'JetBrains Mono', monospace";
            ctx.fillText(pos.label, pos.x + 10, pos.y + 4);
        });
    } catch (err) {
        console.error(err);
    }
}

// ==========================================================================
// Audio Feedback Settings Controller
// ==========================================================================
function initAudioSettings() {
    const toggle = document.getElementById("sound-toggle");
    const slider = document.getElementById("sound-volume-slider");
    const label = document.getElementById("sound-volume-label");
    const badge = document.getElementById("sound-status-badge");
    const testSuccessBtn = document.getElementById("test-sound-success-btn");
    const testErrorBtn = document.getElementById("test-sound-error-btn");
    const testAlertBtn = document.getElementById("test-sound-alert-btn");
    const testClickBtn = document.getElementById("test-sound-click-btn");

    if (!window.NetSentinelSound) return;

    function updateBadge(active) {
        if (!badge) return;
        if (active) {
            badge.className = "badge badge-success";
            badge.innerHTML = '<i class="fa-solid fa-check" style="font-size: 0.65rem; margin-right: 4px;"></i> Enabled';
        } else {
            badge.className = "badge badge-muted";
            badge.innerHTML = '<i class="fa-solid fa-volume-xmark" style="font-size: 0.65rem; margin-right: 4px;"></i> Disabled';
        }
    }

    const isEnabled = window.NetSentinelSound.isEnabled();
    const volumePercent = Math.round(window.NetSentinelSound.getVolume() * 100);

    if (toggle) {
        toggle.checked = isEnabled;
        toggle.setAttribute("aria-checked", isEnabled ? "true" : "false");
        updateBadge(isEnabled);

        toggle.addEventListener("change", () => {
            const checked = toggle.checked;
            toggle.setAttribute("aria-checked", checked ? "true" : "false");
            window.NetSentinelSound.setEnabled(checked);
            updateBadge(checked);
            if (checked) {
                window.NetSentinelSound.play("success");
            }
            showNotification(`Sound effects ${checked ? "enabled" : "disabled"}. Preference saved.`, "info");
        });
    }

    if (slider) {
        slider.value = volumePercent;
        if (label) label.textContent = `${volumePercent}%`;

        slider.addEventListener("input", () => {
            const val = parseInt(slider.value, 10) || 0;
            if (label) label.textContent = `${val}%`;
            window.NetSentinelSound.setVolume(val / 100);
        });

        slider.addEventListener("change", () => {
            window.NetSentinelSound.play("click");
            showNotification("Volume level updated.", "info");
        });
    }

    if (testSuccessBtn) testSuccessBtn.addEventListener("click", () => window.NetSentinelSound.play("success"));
    if (testErrorBtn) testErrorBtn.addEventListener("click", () => window.NetSentinelSound.play("error"));
    if (testAlertBtn) testAlertBtn.addEventListener("click", () => window.NetSentinelSound.play("alert"));
    if (testClickBtn) testClickBtn.addEventListener("click", () => window.NetSentinelSound.play("click"));
}