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
const _TELEMETRY_BASE_MS = 5000;
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

document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    loadOverviewData();
    loadInvestigations();
    loadDevices();
    loadAnalysisHistory();
    initForms();
    initTelemetryChart();
    initGlobalSearch();
});

// Pause polling when the tab is hidden; resume when visible again.
document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        _stopTelemetryInterval();
    } else if (!telemetryPaused) {
        _startTelemetryInterval();
        loadTelemetryGraph();
    }
});

// Prevent default drag and drop behavior across window to prevent browser navigation to file:///
window.addEventListener("dragover", (e) => {
    e.preventDefault();
}, false);

window.addEventListener("drop", (e) => {
    e.preventDefault();
}, false);

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

// View switching with fade animation
function switchView(targetId) {
    const navItems = document.querySelectorAll(".nav-item");
    const viewPanels = document.querySelectorAll(".view-panel");

    // Fade out current views
    viewPanels.forEach(panel => {
        panel.style.opacity = "0";
        panel.style.transition = "opacity 0.3s ease";
    });

    // Remove active classes after transition
    setTimeout(() => {
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
            activePanel.style.display = "block";
            // Trigger reflow for fade-in
            void activePanel.offsetWidth;
            activePanel.style.opacity = "1";
        }

        // Update page title
        const titleText = activeNav ? activeNav.textContent.trim() : "Net Sentinel";
        document.getElementById("current-page-title").textContent = titleText;
    }, 300);

        // Special handling for overview or analytics to restart charts
        if (targetId === "overview-view") {
            setTimeout(renderTelemetryChart, 350);
        } else if (targetId === "analytics-view") {
            setTimeout(() => loadAnalyticsData(currentAnalyticsRange), 350);
        } else if (targetId === "devices-view") {
            loadDevices();
        } else if (targetId === "network-view") {
            loadAnalysisHistory();
        }
}

// Load overview metrics from API
async function loadOverviewData() {
    try {
        const res = await fetch("/api/overview");
        const data = await res.json();
        
        document.getElementById("stat-investigations").textContent = data.investigations_count;
        document.getElementById("stat-devices").textContent = data.devices_count;
        document.getElementById("stat-baselines").textContent = data.integrity_baselines_count;
        document.getElementById("stat-alerts").textContent = data.recent_investigations.length;

        const recentList = document.getElementById("recent-investigations-list");
        if (data.recent_investigations && data.recent_investigations.length > 0) {
            recentList.innerHTML = data.recent_investigations.map(inv => `
                <div style="padding: 8px 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <div><strong>${escapeHtml(inv.id)}</strong>: ${escapeHtml(inv.title)}</div>
                    <span class="badge badge-info">${escapeHtml(inv.status)}</span>
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

// --- Telemetry Chart & Live Feed ---
function renderTelemetryChart() {
    if (!latestTelemetryData || !latestTelemetryData.series) return;
    const canvas = document.getElementById("telemetry-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const metric = document.getElementById("telemetry-metric").value;

    const containerWidth = canvas.parentElement ? canvas.parentElement.clientWidth : 600;
    canvas.width = Math.max(containerWidth - 24, 300);
    canvas.height = 180;

    const series = latestTelemetryData.series;
    const values = series.map(s => {
        if (metric === "bandwidth") return s.inbound_mbps;
        if (metric === "packets") return s.packets_per_sec;
        return s.latency_ms;
    });

    const maxVal = Math.max(...values, 10);
    const minVal = 0;
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw subtle grid lines
    ctx.strokeStyle = "rgba(38, 53, 79, 0.6)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
        let y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Draw time-series line with refined SOC accents
    ctx.strokeStyle = metric === "latency" ? "#f59e0b" : "#10b981";
    ctx.lineWidth = 2.5;
    ctx.beginPath();

    const stepX = width / (values.length - 1 || 1);
    values.forEach((val, idx) => {
        const x = idx * stepX;
        const y = height - ((val - minVal) / (maxVal - minVal || 1)) * (height - 24) - 12;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Update Header Stats
    if (metric === "bandwidth") {
        const peak = Math.max(...series.map(s => s.inbound_mbps));
        document.getElementById("telemetry-stat-primary").textContent = `Peak Inbound: ${peak} Mbps`;
        const avgLat = (series.reduce((acc, s) => acc + s.latency_ms, 0) / series.length).toFixed(1);
        document.getElementById("telemetry-stat-secondary").textContent = `Avg Latency: ${avgLat} ms`;
    } else if (metric === "packets") {
        const peakPps = Math.max(...series.map(s => s.packets_per_sec));
        document.getElementById("telemetry-stat-primary").textContent = `Peak Rate: ${peakPps} pps`;
        document.getElementById("telemetry-stat-secondary").textContent = `Source: Standalone Agent`;
    } else {
        const peakLat = Math.max(...series.map(s => s.latency_ms));
        document.getElementById("telemetry-stat-primary").textContent = `Peak Latency: ${peakLat} ms`;
        document.getElementById("telemetry-stat-secondary").textContent = `Status: Stable`;
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
    const el = document.getElementById("telemetry-stat-secondary");
    if (!el) return;
    if (ok) {
        const now = new Date();
        el.textContent = `Updated ${now.toTimeString().slice(0, 8)} UTC`;
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
}

// Reset attack simulation — clears demo state and the results table.
async function resetAttackSimulation() {
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

    const tbody = document.querySelector("#network-events-table tbody");
    if (tbody) {
        if (data && data.events && data.events.length > 0) {
            tbody.innerHTML = data.events.map(e => {
                const sev = (e.severity || "low").toLowerCase();
                const badgeClass = sev === "high" || sev === "danger" ? "badge-danger" : sev === "medium" || sev === "warning" ? "badge-warning" : "badge-success";
                return `
                    <tr>
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
                    <td><span class="badge badge-success">${escapeHtml(inv.status)}</span></td>
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
                    showNotification("Server returned non-JSON response (status " + res.status + ")", "error");
                    return;
                }

                if (res.ok) {
                    loadNetworkResults(data);
                    loadAnalysisHistory();
                    showNotification(`Analysis complete: ${data.events.length} suspicious events detected out of ${data.summary && data.summary.total_records_analyzed ? data.summary.total_records_analyzed : data.events.length} records.`, data.events.length > 0 ? "warning" : "success");
                    const container = document.getElementById("network-results-container");
                    if (container) container.scrollIntoView({ behavior: "smooth", block: "nearest" });
                } else {
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
            }
        });
    }

    if (embedForm) {
        embedForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = embedImageInput ? embedImageInput.files[0] : null;
            const secret = document.getElementById("embed-secret").value;
            if (!file) {
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
                    const downloadHref = data.image_data || data.download_url;
                    const fileName = data.filename || "encoded_image.png";
                    box.innerHTML = `
                        <div style="margin-bottom: 8px;">✅ ${escapeHtml(data.message)}</div>
                        ${data.image_data ? `<img src="${data.image_data}" alt="Encoded Preview" style="max-height: 100px; display: block; border-radius: 6px; margin: 8px 0; border: 1px solid var(--border-color);" />` : ''}
                        <a href="${downloadHref}" class="btn btn-primary" style="margin-top: 6px; display: inline-block;" download="${escapeHtml(fileName)}">
                            <i class="fa-solid fa-download"></i> Download Encoded PNG
                        </a>
                    `;
                } else {
                    box.innerHTML = `❌ Error: ${escapeHtml(data.detail)}`;
                }
            } catch (err) {
                showNotification("Embedding failed.", "error");
            }
        });
    }

    // 3. Extract Form
    const extractForm = document.getElementById("extract-form");
    if (extractForm) {
        extractForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("extract-image");
            const file = fileInput && fileInput.files ? fileInput.files[0] : null;
            if (!file) {
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
                    document.getElementById("extracted-text-output").textContent = data.secret;
                } else {
                    document.getElementById("extracted-text-output").textContent = data.detail || "Extraction failed.";
                }
            } catch (err) {
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
                        previewBox.style.textAlign = "center";
                        forensicsFile.parentNode.appendChild(previewBox);
                    }
                    previewBox.innerHTML = `
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 6px;">
                            Selected: <strong>${escapeHtml(file.name)}</strong> (${(file.size / 1024).toFixed(1)} KB)
                        </div>
                        <img src="${currentForensicsPreviewUrl}" alt="Local Forensics Preview" style="max-height: 140px; max-width: 100%; border-radius: 8px; border: 1px solid var(--border-color); object-fit: contain; margin: 0 auto; display: block;" />
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
                showNotification("Please select an image file.", "error");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/forensics/analyze", { method: "POST", body: formData });
                const data = await res.json();
                const container = document.getElementById("forensics-results");
                container.classList.remove("hidden");
                const details = document.getElementById("forensics-details");
                details.innerHTML = `
                    <div><strong>Filename:</strong> ${escapeHtml(data.filename)}</div>
                    <div><strong>Format:</strong> ${escapeHtml(data.format)} (${escapeHtml(data.mode)})</div>
                    <div><strong>Dimensions:</strong> ${escapeHtml(data.dimensions)}</div>
                    <div><strong>File Size:</strong> ${escapeHtml(data.file_size_bytes)} bytes</div>
                    <div><strong>SHA-256:</strong> <code>${escapeHtml(data.sha256)}</code></div>
                    <div><strong>Susposity Score:</strong> <span class="badge badge-warning">${escapeHtml(data.susposity_score)} / 100</span></div>
                    <div style="grid-column: span 2;"><strong>Heuristic Indicators:</strong><ul>${(data.indicators || []).map(i => `<li>${escapeHtml(i)}</li>`).join("")}</ul></div>
                `;
            } catch (err) {
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
                const box = document.getElementById("integrity-result");
                box.classList.remove("hidden");
                
                let matchHtml = "";
                if (data.reference_hash) {
                    matchHtml = data.match 
                        ? `<p style="color: var(--success); font-weight: bold; margin-top: 8px;">✅ Hash MATCHES trusted reference.</p>` 
                        : `<p style="color: var(--danger); font-weight: bold; margin-top: 8px;">❌ Hash MISMATCH with reference!</p>`;
                }

                box.innerHTML = `
                    <strong>File:</strong> ${escapeHtml(data.filename)}<br>
                    <strong>Computed SHA-256:</strong> <code>${escapeHtml(data.current_sha256)}</code>
                    ${matchHtml}
                `;
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
                    closeModal();
                    loadInvestigations();
                    loadOverviewData();
                    newInvForm.reset();
                    showNotification("Investigation case created successfully", "success");
                } else {
                    showNotification("Failed to create investigation.", "error");
                }
            } catch (err) {
                showNotification("Request failed.", "error");
            }
        });
    }
}

// Notification system
function showNotification(message, type = "info") {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.position = 'fixed';
    notification.style.top = '24px';
    notification.style.right = '24px';
    notification.style.padding = '12px 20px';
    notification.style.borderRadius = '8px';
    notification.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    notification.style.zIndex = '1001';
    notification.style.backgroundColor = type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#ef4444';
    notification.style.color = '#ffffff';
    notification.style.fontFamily = 'Inter, sans-serif';
    notification.style.fontSize = '0.875rem';
    notification.style.fontWeight = '500';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function showNetworkError() {
    const notification = document.createElement('div');
    notification.className = 'notification notification-error';
    notification.style.cssText = `
        position: fixed;
        top: 24px;
        right: 24px;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1001;
        background-color: #ef4444;
        color: #ffffff;
        font-family: Inter, sans-serif;
        font-size: 0.875rem;
        font-weight: 500;
    `;
    notification.textContent = 'Network analysis request failed';
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
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
                    <td><button class="btn btn-sm btn-outline-danger" onclick="deleteDevice('${encodeURIComponent(dev.id)}')" title="Remove Device"><i class="fa-solid fa-trash"></i></button></td>
                </tr>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed to load devices", err);
        showNotification(err.message, "error");
    }
}

function openNewDeviceModal() {
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
        showNotification("Device added successfully", "success");
        closeDeviceModal();
        loadDevices();
        loadOverviewData();
    } catch (err) {
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
        showNotification("Device removed successfully", "success");
        loadDevices();
        loadOverviewData();
    } catch (err) {
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

    function openResult(viewId) {
        hideDropdown();
        searchInput.value = "";
        switchView(viewId);
    }

    function renderSection(title, items, viewId, titleFn, subtitleFn) {
        if (!items || items.length === 0) return "";
        const header = `<div class="search-category-header">${escapeHtml(title)} (${items.length})</div>`;
        const rows = items.map(item => `
            <div class="search-result-item" onclick="switchView('${viewId}'); document.getElementById('search-results-dropdown').classList.add('hidden');">
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
        closeDeviceModal();
        closeModal();
    });

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
}

// Modal management
function openNewInvestigationModal() {
    document.getElementById("investigation-modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("investigation-modal").classList.add("hidden");
}

// Report generation with safe Blob download
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

        // Trigger safe client-side download via Blob URL
        const jsonBlob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const blobUrl = URL.createObjectURL(jsonBlob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `net_sentinel_report_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        showNotification("Investigation report exported successfully", "success");
    } catch (err) {
        showNotification("Failed to generate report.", "error");
    }
}

// ==========================================================================
// Network Security Analytics Controller (24H, 7D, 30D, 90D)
// ==========================================================================
let currentAnalyticsRange = "24H";
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
    if (m_tp_val) m_tp_val.textContent = m.throughput.value;
    const m_tp_pill = document.getElementById("m-tp-pill");
    if (m_tp_pill) {
        const sign = m.throughput.change_pct >= 0 ? "+" : "";
        m_tp_pill.innerHTML = `<i class="fa-solid fa-arrow-trend-${m.throughput.change_pct >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.throughput.change_pct}%`;
        m_tp_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.throughput.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-tp-chart", m.throughput.bars, m.throughput.favorable ? "#10b981" : "#f43f5e");

    // 3. Metric 2: Threat Events
    const m_threat_val = document.getElementById("m-threat-val");
    if (m_threat_val) m_threat_val.textContent = m.threats.value;
    const m_threat_pill = document.getElementById("m-threat-pill");
    if (m_threat_pill) {
        const sign = m.threats.change_pct >= 0 ? "+" : "";
        m_threat_pill.innerHTML = `<i class="fa-solid fa-arrow-trend-${m.threats.change_pct >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.threats.change_pct}%`;
        m_threat_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.threats.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-threat-chart", m.threats.bars, m.threats.favorable ? "#38bdf8" : "#f43f5e");

    // 4. Metric 3: Active Hosts
    const m_hosts_val = document.getElementById("m-hosts-val");
    if (m_hosts_val) m_hosts_val.textContent = m.hosts.value;
    const m_hosts_pill = document.getElementById("m-hosts-pill");
    if (m_hosts_pill) {
        const sign = m.hosts.change_abs >= 0 ? "+" : "";
        m_hosts_pill.innerHTML = `<i class="fa-solid fa-arrow-${m.hosts.change_abs >= 0 ? 'up' : 'down'} text-[9px]"></i> ${sign}${m.hosts.change_abs} hosts`;
        m_hosts_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.hosts.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-hosts-chart", m.hosts.bars, "#38bdf8");

    // 5. Metric 4: Average Latency
    const m_lat_val = document.getElementById("m-lat-val");
    if (m_lat_val) m_lat_val.textContent = m.latency.value;
    const m_lat_pill = document.getElementById("m-lat-pill");
    if (m_lat_pill) {
        const sign = m.latency.change_diff >= 0 ? "+" : "";
        m_lat_pill.innerHTML = `<i class="fa-solid fa-arrow-${m.latency.change_diff <= 0 ? 'down' : 'up'} text-[9px]"></i> ${sign}${m.latency.change_diff} ms`;
        m_lat_pill.className = `inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded font-mono ${m.latency.favorable ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'}`;
    }
    renderMiniBars("m-lat-chart", m.latency.bars, m.latency.favorable ? "#10b981" : "#f59e0b");

    // 6. Main Telemetry SVG Area Chart
    renderAnalyticsSvgChart(data.chart_series);
}

function renderMiniBars(containerId, values, barColor) {
    const el = document.getElementById(containerId);
    if (!el || !values || !values.length) return;
    const max = Math.max(...values, 1);
    el.innerHTML = values.map(v => {
        const hPct = Math.max(12, Math.round((v / max) * 100));
        return `<span class="flex-1 rounded-sm opacity-80 hover:opacity-100 transition-all cursor-pointer" style="height: ${hPct}%; background-color: ${barColor};" title="${v}"></span>`;
    }).join("");
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

    const inPolyline = inPoints.map(p => `${p.x},${p.y}`).join(" ");
    const outPolyline = outPoints.map(p => `${p.x},${p.y}`).join(" ");
    const inArea = `0,${H} ` + inPolyline + ` ${W},${H}`;
    const outArea = `0,${H} ` + outPolyline + ` ${W},${H}`;

    svg.innerHTML = `
        <defs>
            <linearGradient id="inboundGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.25"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
            </linearGradient>
            <linearGradient id="outboundGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.18"/>
                <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0"/>
            </linearGradient>
        </defs>

        <!-- Subtle Grid Lines -->
        <line x1="0" y1="40" x2="${W}" y2="40" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>
        <line x1="0" y1="90" x2="${W}" y2="90" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>
        <line x1="0" y1="140" x2="${W}" y2="140" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>

        <!-- Inbound Area & Path -->
        <polygon points="${inArea}" fill="url(#inboundGradient)" />
        <polyline fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${inPolyline}" />

        <!-- Outbound Area & Path -->
        <polygon points="${outArea}" fill="url(#outboundGradient)" />
        <polyline fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${outPolyline}" />

        <!-- Interactive Data Dots -->
        ${inPoints.map(p => `<circle cx="${p.x}" cy="${p.y}" r="3.5" fill="#10b981" stroke="#090e1c" stroke-width="1.5"><title>Inbound: ${p.pt.inbound_mbps} Mbps (${p.pt.timestamp})</title></circle>`).join("")}
        ${outPoints.map(p => `<circle cx="${p.x}" cy="${p.y}" r="3" fill="#38bdf8" stroke="#090e1c" stroke-width="1.5"><title>Outbound: ${p.pt.outbound_mbps} Mbps (${p.pt.timestamp})</title></circle>`).join("")}
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