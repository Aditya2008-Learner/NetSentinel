// Net Sentinel Frontend Controller
let telemetryLiveInterval = null;
let telemetryPaused = false;
let latestTelemetryData = null;
let localSimulationActive = false;
let localActiveScenario = null;

// Sequence counter: incremented on every fetch so stale responses are discarded.
let _telemetrySeq = 0;
// True while a fetch is in flight — prevents overlapping requests.
let _telemetryInFlight = false;
// Consecutive failure count for bounded backoff.
let _telemetryFailCount = 0;
const _TELEMETRY_BASE_MS = 5000;
const _TELEMETRY_MAX_BACKOFF_MS = 30000;

document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    loadOverviewData();
    loadInvestigations();
    initForms();
    initTelemetryChart();
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

    // Special handling for overview to restart telemetry chart
    if (targetId === "overview-view") {
        setTimeout(renderTelemetryChart, 350);
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
                    <div><strong>${inv.id}</strong>: ${inv.title}</div>
                    <span class="badge badge-info">${inv.status}</span>
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
    loadTelemetryGraph();
    _startTelemetryInterval();
    window.addEventListener("resize", renderTelemetryChart);
}

// --- Network Log Analysis ---
async function loadNetworkResults(data) {
    const container = document.getElementById("network-results-container");
    container.classList.remove("hidden");

    const summary = data.summary;
    const pills = document.getElementById("network-summary-stats");
    pills.innerHTML = `
        <span class="badge badge-info">Total Events: ${summary.total}</span>
        <span class="badge badge-danger">High Severity: ${summary.by_severity.high}</span>
        <span class="badge badge-warning">Medium Severity: ${summary.by_severity.medium}</span>
        <span class="badge badge-success">Low Severity: ${summary.by_severity.low}</span>
    `;

    const tbody = document.querySelector("#network-events-table tbody");
    if (data.events && data.events.length > 0) {
        tbody.innerHTML = data.events.map(e => `
            <tr>
                <td>${e.timestamp}</td>
                <td><span class="badge badge-${e.severity}">${e.severity}</span></td>
                <td><code>${e.rule_id}</code></td>
                <td><code>${e.src_ip}</code></td>
                <td><code>${e.dst_ip}</code></td>
                <td>${e.observed_label}</td>
                <td>${e.recommended_action}</td>
            </tr>
        `).join("");
    } else {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 20px;">
                    No suspicious events detected across ${summary.total_records_analyzed || summary.total || 0} analyzed records.
                    All network traffic is within normal heuristic thresholds.
                </td>
            </tr>
        `;
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
                    <td><code>${inv.id}</code></td>
                    <td><strong>${inv.title}</strong></td>
                    <td>${inv.case_ref || "N/A"}</td>
                    <td><span class="badge badge-success">${inv.status}</span></td>
                    <td>${inv.created_at}</td>
                </tr>
            `).join("");
        })
        .catch(err => {
            console.error("Failed to load investigations", err);
        });
}

// Form initialization
function initForms() {
    // Network Analysis Form
    const netForm = document.getElementById("network-upload-form");
    if (netForm) {
        let submitCount = 0;
        netForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("log-file-input");
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            // Get and disable the submit button
            const analyzeBtn = netForm.querySelector('button[type="submit"]');
            if (!analyzeBtn) return;
            const originalText = analyzeBtn.textContent || "Analyze Traffic Logs";
            analyzeBtn.setAttribute("disabled", "true");
            analyzeBtn.textContent = "Analyzing...";

            // Prevent duplicate submissions
            if (submitCount > 0) {
                showNotification("Analysis already in progress. Please wait for results.", "error");
                analyzeBtn.removeAttribute("disabled");
                analyzeBtn.textContent = originalText;
                submitCount--;
                return;
            }
            submitCount++;

            try {
                const res = await fetch("/api/network/analyze", {
                    method: "POST",
                    body: formData
                });
                let data;
                try {
                    data = await res.json();
                } catch (_) {
                    // Non-JSON response
                    const txt = await res.text();
                    showNotification("Server returned invalid data (status " + res.status + ")", "error");
                    analyzeBtn.removeAttribute("disabled");
                    analyzeBtn.textContent = originalText;
                    submitCount--;
                    return;
                }

                if (res.ok) {
                    loadNetworkResults(data);
                } else {
                    showNotification(data.detail || "Analysis failed", "error");
                }
            } catch (err) {
                showNetworkError();
            } finally {
                analyzeBtn.removeAttribute("disabled");
                analyzeBtn.textContent = originalText;
                submitCount--;
            }
        });
    }

    // Embed Form
    const embedForm = document.getElementById("embed-form");
    if (embedForm) {
        embedForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = document.getElementById("embed-image").files[0];
            const secret = document.getElementById("embed-secret").value;
            const formData = new FormData();
            formData.append("file", file);
            formData.append("secret", secret);

            try {
                const res = await fetch("/api/stego/embed", { method: "POST", body: formData });
                const data = await res.json();
                const box = document.getElementById("embed-result");
                box.classList.remove("hidden");
                if (res.ok) {
                    box.innerHTML = `✅ ${data.message}<br><a href="${data.download_url}" class="btn btn-primary" style="margin-top: 10px;" download>Download Encoded PNG</a>`;
                } else {
                    box.innerHTML = `❌ Error: ${data.detail}`;
                }
            } catch (err) {
                alert("Embedding failed.");
            }
        });
    }

    // Extract Form
    const extractForm = document.getElementById("extract-form");
    if (extractForm) {
        extractForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = document.getElementById("extract-image").files[0];
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
                alert("Extraction request failed.");
            }
        });
    }

    // Forensics Form
    const forensicsForm = document.getElementById("forensics-form");
    if (forensicsForm) {
        forensicsForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = document.getElementById("forensics-file").files[0];
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/forensics/analyze", { method: "POST", body: formData });
                const data = await res.json();
                const container = document.getElementById("forensics-results");
                container.classList.remove("hidden");
                const details = document.getElementById("forensics-details");
                details.innerHTML = `
                    <div><strong>Filename:</strong> ${data.filename}</div>
                    <div><strong>Format:</strong> ${data.format} (${data.mode})</div>
                    <div><strong>Dimensions:</strong> ${data.dimensions}</div>
                    <div><strong>File Size:</strong> ${data.file_size_bytes} bytes</div>
                    <div><strong>SHA-256:</strong> <code>${data.sha256}</code></div>
                    <div><strong>Susposity Score:</strong> <span class="badge badge-warning">${data.susposity_score} / 100</span></div>
                    <div style="grid-column: span 2;"><strong>Heuristic Indicators:</strong><ul>${data.indicators.map(i => `<li>${i}</li>`).join("")}</ul></div>
                `;
            } catch (err) {
                alert("Forensics analysis failed.");
            }
        });
    }

    // Integrity Form
    const integrityForm = document.getElementById("integrity-form");
    if (integrityForm) {
        integrityForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = document.getElementById("integrity-file").files[0];
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
                    <strong>File:</strong> ${data.filename}<br>
                    <strong>Computed SHA-256:</strong> <code>${data.current_sha256}</code>
                    ${matchHtml}
                `;
            } catch (err) {
                alert("Integrity verification failed.");
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
                    alert("Failed to create investigation.");
                }
            } catch (err) {
                alert("Request failed.");
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
    notification.style.backgroundColor = type === 'success' ? '#10b981' : '#ef4444';
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

// Modal management
function openNewInvestigationModal() {
    document.getElementById("investigation-modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("investigation-modal").classList.add("hidden");
}

// Report generation
async function generateReport() {
    try {
        const res = await fetch("/api/reports/export");
        const data = await res.json();
        const preview = document.getElementById("report-preview");
        preview.classList.remove("hidden");
        document.getElementById("report-json-output").textContent = JSON.stringify(data, null, 2);
    } catch (err) {
        alert("Failed to generate report.");
    }
}