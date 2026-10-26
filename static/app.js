// Net Sentinel Frontend Controller
let telemetryLiveInterval = null;
let telemetryPaused = false;
let latestTelemetryData = null;

document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    loadOverviewData();
    loadInvestigations();
    initForms();
    initTelemetryChart();
});

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

function switchView(targetId) {
    document.querySelectorAll(".nav-item").forEach(nav => nav.classList.remove("active"));
    document.querySelectorAll(".view-panel").forEach(panel => panel.classList.remove("active"));

    const activeNav = document.querySelector(`.nav-item[data-target="${targetId}"]`);
    const activePanel = document.getElementById(targetId);

    if (activeNav) activeNav.classList.add("active");
    if (activePanel) {
        activePanel.classList.add("active");
        const titleText = activeNav ? activeNav.textContent.trim() : "Dashboard";
        document.getElementById("current-page-title").textContent = titleText;
        if (targetId === "overview-view") {
            setTimeout(renderTelemetryChart, 50);
        }
    }
}

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
                <div style="padding: 10px 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <div><strong>${inv.id}</strong>: ${inv.title}</div>
                    <span class="badge badge-info">${inv.status}</span>
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Failed to load overview metrics", err);
    }
}

// --- Telemetry Chart & Live Feed ---
async function loadTelemetryGraph() {
    const range = document.getElementById("telemetry-range").value;
    try {
        const res = await fetch(`/api/telemetry?range=${range}`);
        const data = await res.json();
        latestTelemetryData = data;
        
        const banner = document.getElementById("simulation-banner");
        if (banner) {
            if (data.simulation_active) {
                banner.style.display = "inline-block";
                banner.textContent = `⚠️ DEMO MODE — SIMULATED ATTACK ACTIVE (${data.active_scenario.toUpperCase()})`;
            } else {
                banner.style.display = "none";
            }
        }

        renderTelemetryChart();
    } catch (err) {
        console.error("Failed to load telemetry feed", err);
    }
}

async function triggerAttackSimulation() {
    const scenario = document.getElementById("attack-scenario").value;
    const formData = new URLSearchParams();
    formData.append("scenario", scenario);

    try {
        const res = await fetch("/api/telemetry/simulate", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            loadTelemetryGraph();
            if (data.simulated_events && data.simulated_events.length > 0) {
                // Render into network security table silently without forcing tab switch
                renderNetworkResults({ 
                    events: data.simulated_events, 
                    summary: { total: data.simulated_events.length, by_severity: { high: 1, medium: 0, low: 0 } } 
                });
            }
        } else {
            alert(data.detail || "Simulation failed");
        }
    } catch (err) {
        alert("Simulation request failed.");
    }
}

async function resetAttackSimulation() {
    const formData = new URLSearchParams();
    formData.append("scenario", "reset");

    try {
        await fetch("/api/telemetry/simulate", {
            method: "POST",
            body: formData
        });
        loadTelemetryGraph();
    } catch (err) {
        alert("Reset failed.");
    }
}

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
    ctx.strokeStyle = "#1f2937";
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
        let y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Draw time-series line
    ctx.strokeStyle = metric === "latency" ? "#f59e0b" : "#f47721";
    ctx.lineWidth = 2;
    ctx.beginPath();

    const stepX = width / (values.length - 1 || 1);
    values.forEach((val, idx) => {
        const x = idx * stepX;
        const y = height - ((val - minVal) / (maxVal - minVal || 1)) * (height - 20) - 10;
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

function toggleTelemetryLive() {
    telemetryPaused = !telemetryPaused;
    const btn = document.getElementById("telemetry-toggle-btn");
    if (telemetryPaused) {
        btn.innerHTML = `<i class="fa-solid fa-play"></i> Resume`;
        clearInterval(telemetryLiveInterval);
    } else {
        btn.innerHTML = `<i class="fa-solid fa-pause"></i> Pause`;
        telemetryLiveInterval = setInterval(loadTelemetryGraph, 5000);
    }
}

function initTelemetryChart() {
    loadTelemetryGraph();
    telemetryLiveInterval = setInterval(loadTelemetryGraph, 5000);
    window.addEventListener("resize", renderTelemetryChart);
}

async function loadInvestigations() {
    try {
        const res = await fetch("/api/investigations");
        const investigations = await res.json();
        const tbody = document.querySelector("#investigations-table tbody");
        if (!tbody) return;

        if (investigations.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #94a3b8;">No investigation cases found.</td></tr>`;
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
    } catch (err) {
        console.error("Failed to load investigations", err);
    }
}

function initForms() {
    // Network Analysis Form
    const netForm = document.getElementById("network-upload-form");
    if (netForm) {
        netForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("log-file-input");
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);

            try {
                const res = await fetch("/api/network/analyze", {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    renderNetworkResults(data);
                } else {
                    alert(data.detail || "Analysis failed");
                }
            } catch (err) {
                alert("Network analysis request failed.");
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
                } else {
                    alert("Failed to create investigation.");
                }
            } catch (err) {
                alert("Request failed.");
            }
        });
    }
}

function renderNetworkResults(data) {
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
}

function openNewInvestigationModal() {
    document.getElementById("investigation-modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("investigation-modal").classList.add("hidden");
}

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
