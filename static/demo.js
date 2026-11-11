/**
 * NetSentinel — Global Interactive Demo Controller (`window.NetSentinelDemo`)
 * Provides end-to-end interactive simulation walks, state management, and feature walkthroughs.
 * Strict CSP compliant: zero inline event handlers, uses event delegation and explicit listeners.
 */

(function (window) {
    'use strict';

    // State variables with lifecycle state machine
    let demoState = {
        status: 'IDLE',
        active: false,
        currentFeature: 'network_monitor',
        bandwidthMultiplier: 1.0,
        packetRateMultiplier: 1.0,
        collectorHealth: 'LIVE',
        demoTelemetryInterval: null
    };

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#039;');
    }

    /**
     * Initializes event listeners, TRY DEMO buttons, banner controls, and modals.
     */
    function init() {
        // 1. Attach click handlers to all "TRY DEMO" buttons
        document.querySelectorAll('.try-demo-btn:not(#top-nav-demo-toggle-btn)').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const feature = btn.getAttribute('data-feature') || 'network_monitor';
                enable(feature);
            });
        });

        // 2. Attach toggle listener on sidebar demo badge
        const sidebarBadge = document.getElementById('sidebar-demo-badge');
        if (sidebarBadge) {
            sidebarBadge.addEventListener('click', () => {
                if (demoState.active) {
                    disable();
                } else {
                    enable('network_monitor');
                }
            });
        }

        // 3. Top nav demo toggle button
        const topNavDemoBtn = document.getElementById('top-nav-demo-toggle-btn');
        if (topNavDemoBtn) {
            topNavDemoBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (demoState.active) {
                    disable();
                } else {
                    enable('network_monitor');
                }
            });
        }

        // 4. Wire up Persistent Demo Banner buttons
        const bannerResetBtn = document.getElementById('demo-banner-reset-btn');
        if (bannerResetBtn) {
            bannerResetBtn.addEventListener('click', reset);
        }

        const bannerExitBtn = document.getElementById('demo-banner-exit-btn');
        if (bannerExitBtn) {
            bannerExitBtn.addEventListener('click', disable);
        }

        // 5. Wire up Overview Demo Controls toolbar (slider, spike, portscan)
        const bwSlider = document.getElementById('demo-bandwidth-multiplier');
        const bwLabel = document.getElementById('demo-bandwidth-multiplier-val');
        if (bwSlider) {
            bwSlider.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value) || 1.0;
                if (bwLabel) {
                    bwLabel.textContent = `${val.toFixed(1)}x`;
                }
            });
            bwSlider.addEventListener('change', (e) => {
                updateBandwidth(e.target.value);
            });
        }

        const spikeBtn = document.getElementById('overview-demo-spike-btn');
        if (spikeBtn) {
            spikeBtn.addEventListener('click', () => {
                injectAnomaly('spike');
            });
        }

        const portscanBtn = document.getElementById('overview-demo-portscan-btn');
        if (portscanBtn) {
            portscanBtn.addEventListener('click', () => {
                injectAnomaly('portscan');
            });
        }

        // 6. Threat Intel Modal handlers
        const openThreatModal = () => {
            const modal = document.getElementById('demo-threat-intel-modal');
            if (modal) {
                modal.classList.remove('hidden');
                queryDemoThreatIntel('198.51.100.14');
            }
        };

        const closeThreatModal = () => {
            const modal = document.getElementById('demo-threat-intel-modal');
            if (modal) modal.classList.add('hidden');
        };

        const closeThreatBtn = document.getElementById('close-demo-threat-modal');
        if (closeThreatBtn) closeThreatBtn.addEventListener('click', closeThreatModal);

        const cancelThreatBtn = document.getElementById('cancel-demo-threat-modal-btn');
        if (cancelThreatBtn) cancelThreatBtn.addEventListener('click', closeThreatModal);

        const searchThreatBtn = document.getElementById('demo-ip-search-btn');
        const searchThreatInput = document.getElementById('demo-ip-search');
        if (searchThreatBtn && searchThreatInput) {
            searchThreatBtn.addEventListener('click', () => {
                const ip = (searchThreatInput.value || '').trim();
                if (ip) queryDemoThreatIntel(ip);
            });
            searchThreatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const ip = (searchThreatInput.value || '').trim();
                    if (ip) queryDemoThreatIntel(ip);
                }
            });
        }

        document.querySelectorAll('.demo-ip-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const ip = chip.getAttribute('data-ip');
                if (ip) {
                    if (searchThreatInput) searchThreatInput.value = ip;
                    queryDemoThreatIntel(ip);
                }
            });
        });

        // 7. System Health Modal handlers
        const openHealthModal = () => {
            const modal = document.getElementById('demo-system-health-modal');
            if (modal) {
                modal.classList.remove('hidden');
            }
        };

        const closeHealthModal = () => {
            const modal = document.getElementById('demo-system-health-modal');
            if (modal) modal.classList.add('hidden');
        };

        const closeHealthBtn = document.getElementById('close-demo-health-modal');
        if (closeHealthBtn) closeHealthBtn.addEventListener('click', closeHealthModal);

        const cancelHealthBtn = document.getElementById('cancel-demo-health-modal-btn');
        if (cancelHealthBtn) cancelHealthBtn.addEventListener('click', closeHealthModal);

        document.querySelectorAll('.demo-collector-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const state = btn.getAttribute('data-state');
                toggleCollectorState(state);
            });
        });

        // 8. Event Delegation on tables to eliminate inline onclick CSP violations
        const devicesTbody = document.getElementById('devices-table-body');
        if (devicesTbody && !devicesTbody._hasDemoDelegation) {
            devicesTbody._hasDemoDelegation = true;
            devicesTbody.addEventListener('click', (e) => {
                const inspectBtn = e.target.closest('.demo-inspect-device-btn');
                if (inspectBtn) {
                    e.stopPropagation();
                    const deviceId = inspectBtn.getAttribute('data-device-id');
                    if (deviceId) inspectDevice(deviceId);
                    return;
                }
                const row = e.target.closest('.device-row-clickable');
                if (row) {
                    const deviceId = row.getAttribute('data-device-id');
                    if (deviceId) inspectDevice(deviceId);
                }
            });
        }

        const socAlertsTbody = document.getElementById('soc-alerts-tbody');
        if (socAlertsTbody && !socAlertsTbody._hasDemoDelegation) {
            socAlertsTbody._hasDemoDelegation = true;
            socAlertsTbody.addEventListener('click', (e) => {
                const triageBtn = e.target.closest('.demo-triage-alert-btn');
                if (triageBtn) {
                    e.stopPropagation();
                    const alertId = triageBtn.getAttribute('data-alert-id');
                    if (alertId) triageDemoAlert(alertId);
                }
            });
        }

        // Store modal openers on demo controller
        demoState.openThreatModal = openThreatModal;
        demoState.openHealthModal = openHealthModal;

        // Automatically sync state from backend on load
        fetch('/api/demo/state')
            .then(res => res.json())
            .then(data => {
                if (data && typeof data.bandwidth_multiplier === 'number') {
                    demoState.bandwidthMultiplier = data.bandwidth_multiplier;
                    demoState.packetRateMultiplier = data.packet_rate_multiplier || 1.0;
                    demoState.collectorHealth = data.collector_health || 'LIVE';
                    if (bwSlider) bwSlider.value = demoState.bandwidthMultiplier;
                    if (bwLabel) bwLabel.textContent = `${demoState.bandwidthMultiplier.toFixed(1)}x`;
                }
            })
            .catch(() => {});

        // Check sessionStorage for persisted demo state OR URL query parameter
        const savedActive = sessionStorage.getItem('net_sentinel_demo_active') === 'true';
        const savedFeature = sessionStorage.getItem('net_sentinel_demo_feature');
        const urlParams = new URLSearchParams(window.location.search);
        const demoParam = urlParams.get('demo');

        if (savedActive || demoParam) {
            setTimeout(() => {
                enable(savedFeature || demoParam || 'network_monitor');
            }, 300);
        }
    }

    /**
     * Feature to View ID mapping.
     */
    const FEATURE_VIEW_MAP = {
        network_monitor: 'overview-view',
        analytics: 'analytics-view',
        csv_analysis: 'network-view',
        topology: 'topology-view',
        devices: 'devices-view',
        flows: 'live-collector-view',
        soc_alerts: 'soc-alerts-view',
        investigations: 'investigations-view',
        stego: 'stego-view',
        forensics: 'forensics-view',
        integrity: 'integrity-view',
        reports: 'reports-view',
        health: 'settings-view'
    };

    /**
     * Enables demo mode, shows the persistent demo bar, updates page title, plays feedback sound, shows toast notification, and runs feature demo.
     */
    function enable(featureName) {
        if (!document.getElementById('views-wrapper')) {
            sessionStorage.setItem('net_sentinel_demo_active', 'true');
            sessionStorage.setItem('net_sentinel_demo_feature', featureName || 'network_monitor');
            window.location.href = '/dashboard?demo=' + encodeURIComponent(featureName || 'network_monitor');
            return;
        }

        demoState.status = 'INITIALIZING';
        demoState.active = true;
        demoState.currentFeature = featureName || 'network_monitor';

        sessionStorage.setItem('net_sentinel_demo_active', 'true');
        sessionStorage.setItem('net_sentinel_demo_feature', demoState.currentFeature);

        if (window.NetSentinelSound) {
            window.NetSentinelSound.play('success');
        }

        if (window.sileo) {
            window.sileo.show({
                id: 'demo-enabled-toast',
                type: 'success',
                message: `Demo Mode Enabled: ${formatFeatureName(demoState.currentFeature)}`
            });
        }

        // Show Persistent Demo Banner
        const banner = document.getElementById('persistent-demo-banner');
        if (banner) {
            banner.classList.remove('hidden');
        }

        // Update sidebar badge visual
        const badge = document.getElementById('sidebar-demo-badge');
        const badgeText = document.getElementById('sidebar-demo-badge-text');
        if (badge) {
            badge.style.background = 'rgba(183, 243, 107, 0.15)';
            badge.style.borderColor = '#B7F36B';
            badge.style.color = '#B7F36B';
        }
        if (badgeText) {
            badgeText.textContent = 'Demo Mode: Active';
        }

        const topNavBtn = document.getElementById('top-nav-demo-toggle-btn');
        if (topNavBtn) {
            topNavBtn.innerHTML = '<i class="fa-solid fa-xmark"></i> EXIT DEMO';
            topNavBtn.style.borderColor = 'var(--primary-accent)';
            topNavBtn.style.color = 'var(--primary-accent)';
        }

        demoState.status = 'ACTIVE';

        // Check if mapped view is active; switch if needed and populate view data
        const viewId = FEATURE_VIEW_MAP[demoState.currentFeature];
        if (viewId) {
            const panel = document.getElementById(viewId);
            const isAlreadyActive = panel && panel.classList.contains('active');
            if (!isAlreadyActive && window.switchView) {
                window.switchView(viewId);
            }
        }

        // Populate data for that view
        populateDemoForFeature(demoState.currentFeature);
    }

    /**
     * Exits demo mode, hides demo bar, restores normal view state.
     */
    function disable() {
        demoState.status = 'STOPPING';
        demoState.active = false;
        if (demoState.demoTelemetryInterval) {
            clearInterval(demoState.demoTelemetryInterval);
            demoState.demoTelemetryInterval = null;
        }

        sessionStorage.removeItem('net_sentinel_demo_active');
        sessionStorage.removeItem('net_sentinel_demo_feature');

        if (window.NetSentinelSound) {
            window.NetSentinelSound.play('click');
        }

        if (window.sileo) {
            window.sileo.info('Demo Mode Deactivated');
        }

        // Hide Persistent Demo Banner
        const banner = document.getElementById('persistent-demo-banner');
        if (banner) {
            banner.classList.add('hidden');
        }

        const badge = document.getElementById('sidebar-demo-badge');
        const badgeText = document.getElementById('sidebar-demo-badge-text');
        if (badge) {
            badge.style.background = '';
            badge.style.borderColor = '';
            badge.style.color = '';
        }
        if (badgeText) {
            badgeText.textContent = 'Demo Mode Active';
        }

        const topNavBtn = document.getElementById('top-nav-demo-toggle-btn');
        if (topNavBtn) {
            topNavBtn.innerHTML = '<i class="fa-solid fa-flask"></i> TRY DEMO';
            topNavBtn.style.borderColor = 'var(--accent-amber)';
            topNavBtn.style.color = 'var(--accent-amber)';
        }

        // If on dashboard, reload active view with live data
        if (window.switchView) {
            const activeView = document.querySelector('.view-panel.active');
            if (activeView) {
                const viewId = activeView.id;
                if (viewId === 'overview-view' && window.loadOverviewData) {
                    window.loadOverviewData();
                } else if (window.switchView) {
                    window.switchView(viewId);
                }
            }
        }

        demoState.status = 'IDLE';
    }

    /**
     * Resets demo data via POST /api/demo/reset.
     */
    function reset() {
        fetch('/api/demo/reset', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (window.NetSentinelSound) {
                    window.NetSentinelSound.play('success');
                }
                if (window.sileo) {
                    window.sileo.success('Demo environment successfully reset to pristine defaults.');
                }
                // Reset local multipliers in UI
                demoState.bandwidthMultiplier = 1.0;
                const bwSlider = document.getElementById('demo-bandwidth-multiplier');
                const bwLabel = document.getElementById('demo-bandwidth-multiplier-val');
                if (bwSlider) bwSlider.value = '1.0';
                if (bwLabel) bwLabel.textContent = '1.0x';

                // Reload current view walkthrough, but do not re-open modal features
                if (demoState.currentFeature !== 'health' && demoState.currentFeature !== 'threat_intel') {
                    populateDemoForFeature(demoState.currentFeature);
                }
            })
            .catch(err => {
                if (window.NetSentinelSound) {
                    window.NetSentinelSound.play('error');
                }
                if (window.sileo) {
                    window.sileo.error('Failed to reset demo state.');
                }
            });
    }

    /**
     * Updates bandwidth multiplier.
     */
    function updateBandwidth(val) {
        const mult = parseFloat(val) || 1.0;
        demoState.bandwidthMultiplier = mult;
        const bwLabel = document.getElementById('demo-bandwidth-multiplier-val');
        if (bwLabel) bwLabel.textContent = `${mult.toFixed(1)}x`;

        fetch('/api/demo/state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bandwidth_multiplier: mult })
        })
            .then(res => res.json())
            .then(data => {
                if (window.NetSentinelSound) {
                    window.NetSentinelSound.play('click');
                }
                if (window.sileo) {
                    window.sileo.info(`Bandwidth Multiplier updated to ${mult.toFixed(1)}x`);
                }
                // Refresh network monitor view data
                populateDemoNetworkMonitor();
            })
            .catch(() => {});
    }

    /**
     * Injects an anomaly scenario.
     */
    function injectAnomaly(scenario) {
        if (!scenario) return;
        fetch('/api/demo/state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active_scenario: scenario })
        })
            .then(res => res.json())
            .then(data => {
                if (window.NetSentinelSound) {
                    window.NetSentinelSound.play('alert');
                }
                if (window.sileo) {
                    window.sileo.warning(`Anomaly Injected: ${scenario.toUpperCase()}`);
                }
                // Sync select dropdown in overview if present
                const scenarioSelect = document.getElementById('attack-scenario');
                if (scenarioSelect) scenarioSelect.value = scenario;

                // Trigger chart spike or refresh current view data
                populateDemoNetworkMonitor();
            })
            .catch(() => {});
    }

    /**
     * Toggles collector health state.
     */
    function toggleCollectorState(state) {
        const upper = (state || 'LIVE').toUpperCase();
        demoState.collectorHealth = upper;

        // Update button active styling in health modal
        document.querySelectorAll('.demo-collector-toggle-btn').forEach(btn => {
            if (btn.getAttribute('data-state') === upper) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        fetch('/api/demo/state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ collector_health: upper })
        })
            .then(res => res.json())
            .then(data => {
                if (window.NetSentinelSound) {
                    window.NetSentinelSound.play(upper === 'LIVE' ? 'success' : 'alert');
                }
                if (window.sileo) {
                    window.sileo.info(`Collector Status changed to: ${upper}`);
                }
                populateDemoSystemHealth();
            })
            .catch(() => {});
    }

    // ==========================================================================
    // Feature Walkthrough Handlers
    // ==========================================================================

    function runFeatureWalkthrough(feature) {
        switch (feature) {
            case 'network_monitor':
                demoNetworkMonitor();
                break;
            case 'analytics':
                demoAnalytics();
                break;
            case 'csv_analysis':
                demoCsvAnalysis();
                break;
            case 'topology':
                demoTopology();
                break;
            case 'devices':
                demoDeviceInventory();
                break;
            case 'flows':
                demoFlowExplorer();
                break;
            case 'threat_intel':
                demoThreatIntel();
                break;
            case 'soc_alerts':
                demoSocAlerts();
                break;
            case 'investigations':
                demoInvestigations();
                break;
            case 'stego':
                demoStego();
                break;
            case 'forensics':
                demoImageForensics();
                break;
            case 'integrity':
                demoIntegrity();
                break;
            case 'reports':
                demoReports();
                break;
            case 'health':
                demoSystemHealth();
                break;
            default:
                demoNetworkMonitor();
                break;
        }
    }

    function formatFeatureName(feat) {
        const map = {
            network_monitor: 'Network Security & Telemetry',
            analytics: 'Security Analytics & Trends',
            csv_analysis: 'Log Analysis & Threat Ingestion',
            topology: 'Network Intelligence & Topology',
            devices: 'Device & Host Inventory',
            flows: 'Live Collector & Flow Explorer',
            threat_intel: 'Threat Intelligence Lookup',
            soc_alerts: 'SOC Security Alert Triage',
            investigations: 'Digital Forensics Investigations',
            stego: 'Steganography Lab & Payload Extraction',
            forensics: 'Image Forensics & Heuristics',
            integrity: 'File Integrity Verification',
            reports: 'Consolidated Audit Reports',
            health: 'System Health & Collector Status'
        };
        return map[feat] || 'Security Demo';
    }

    function populateDemoNetworkMonitor() {
        fetch('/api/demo/telemetry?range=1h')
            .then(res => res.json())
            .then(data => {
                const series = data.series || [];
                if (series.length > 0 && window.updateTelemetrySeriesWithLiveMeasurements) {
                    const latest = series[series.length - 1];
                    window.updateTelemetrySeriesWithLiveMeasurements(latest.bandwidth_mbps, latest.bandwidth_mbps * 0.75, latest);
                }
                if (window.loadTelemetryGraph) {
                    window.loadTelemetryGraph();
                }
            })
            .catch(() => {});
    }

    function populateDemoAnalytics() {
        if (window.sileo) {
            window.sileo.info('Loaded SOC Network Security Analytics demo telemetry.');
        }
    }

    function populateDemoCsvAnalysis() {
        fetch('/api/demo/files/csv')
            .then(res => {
                if (!res.ok) throw new Error('Could not fetch demo CSV');
                return res.text();
            })
            .then(csvText => {
                const blob = new Blob([csvText], { type: 'text/csv' });
                const file = new File([blob], 'net_sentinel_demo_logs.csv', { type: 'text/csv' });
                const logFileInput = document.getElementById('log-file-input');
                if (logFileInput) {
                    try {
                        const dt = new DataTransfer();
                        dt.items.add(file);
                        logFileInput.files = dt.files;
                    } catch (_) {}
                }
                const fileDisplay = document.getElementById('selected-file-display');
                if (fileDisplay) {
                    fileDisplay.style.display = 'block';
                    fileDisplay.innerHTML = `<i class="fa-solid fa-file-csv"></i> <strong>net_sentinel_demo_logs.csv</strong> (${(file.size / 1024).toFixed(1)} KB)`;
                }
                if (window.sileo) {
                // CSV loaded successfully
                }
            })
            .catch(err => {
                if (window.loadSampleCsv) {
                    window.loadSampleCsv();
                }
            });
    }

    function populateDemoTopology() {
        renderDemoTopology();
        if (window.sileo) {
            window.sileo.info('Simulated C2 beacon pulse triggered on topology canvas.');
        }
    }

    function populateDemoDeviceInventory() {
        fetch('/api/demo/devices')
            .then(res => res.json())
            .then(devices => {
                const tbody = document.getElementById('devices-table-body');
                if (!tbody) return;
                tbody.innerHTML = devices.map(dev => `
                    <tr class="device-row-clickable" data-device-id="${escapeHtml(dev.id)}" style="cursor: pointer;" title="Click row or Inspect button to view inspection drawer">
                        <td><code>${escapeHtml(dev.id)}</code></td>
                        <td><code>${escapeHtml(dev.ip_address || 'N/A')}</code></td>
                        <td><code>${escapeHtml(dev.mac_address || 'N/A')}</code></td>
                        <td><span class="badge ${dev.status === 'Active' ? 'badge-success' : 'badge-danger'}">${escapeHtml(dev.status)}</span></td>
                        <td>${escapeHtml(dev.observation_source || 'Demo Sensor')}</td>
                        <td>${escapeHtml(dev.last_seen || 'N/A')}</td>
                        <td><button type="button" class="btn btn-sm btn-secondary demo-inspect-device-btn" data-device-id="${escapeHtml(dev.id)}">Inspect</button></td>
                    </tr>
                `).join('');
            })
            .catch(() => {});
    }

    function inspectDevice(deviceId) {
        if (window.openDeviceInspector) {
            window.openDeviceInspector(deviceId);
        }
    }

    function populateDemoFlowExplorer() {
        fetch('/api/demo/flows')
            .then(res => res.json())
            .then(flows => {
                const tbody = document.getElementById('live-flows-tbody');
                if (!tbody) return;
                tbody.innerHTML = flows.slice(0, 15).map(f => `
                    <tr>
                        <td>${escapeHtml(f.timestamp || 'N/A')}</td>
                        <td><code>${escapeHtml(f.src_ip)}</code></td>
                        <td><code>${escapeHtml(f.dst_ip)}</code></td>
                        <td><code>${escapeHtml(f.src_port)} &rarr; ${escapeHtml(f.dst_port)}</code></td>
                        <td><span class="badge badge-info">${escapeHtml(f.protocol)}</span></td>
                        <td>${escapeHtml(f.packets)}</td>
                        <td>${escapeHtml(f.bytes)} B</td>
                    </tr>
                `).join('');
            })
            .catch(() => {});
    }

    function populateDemoSocAlerts() {
        fetch('/api/demo/alerts')
            .then(res => res.json())
            .then(alerts => {
                const tbody = document.getElementById('soc-alerts-tbody');
                if (!tbody) return;
                tbody.innerHTML = alerts.map(a => `
                    <tr>
                        <td><code>${escapeHtml(a.alert_id)}</code></td>
                        <td><strong>${escapeHtml(a.title)}</strong></td>
                        <td><span class="badge ${a.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}">${escapeHtml(a.severity)}</span></td>
                        <td><code>${Math.round(a.confidence * 100)}%</code></td>
                        <td><code>${escapeHtml(a.source_ip)}</code></td>
                        <td><span class="badge badge-info">${escapeHtml(a.status)}</span></td>
                        <td><button type="button" class="btn btn-sm btn-primary demo-triage-alert-btn" data-alert-id="${escapeHtml(a.alert_id)}">Triage</button></td>
                    </tr>
                `).join('');
            })
            .catch(() => {});
    }

    function populateDemoInvestigations() {
        fetch('/api/demo/cases')
            .then(res => res.json())
            .then(cases => {
                const tbody = document.querySelector('#investigations-table tbody');
                if (!tbody) return;
                tbody.innerHTML = cases.map(c => `
                    <tr>
                        <td><code>${escapeHtml(c.id)}</code></td>
                        <td><strong>${escapeHtml(c.title)}</strong></td>
                        <td>${escapeHtml(c.case_ref || 'INC-DEMO')}</td>
                        <td><span class="badge badge-success">${escapeHtml(c.status || 'Active')}</span></td>
                        <td>${escapeHtml(c.created_at || 'Recently')}</td>
                    </tr>
                `).join('');
                if (window.sileo) {
                    window.sileo.info('Loaded simulated digital forensics incident investigations.');
                }
            })
            .catch(() => {
                if (window.loadInvestigations) window.loadInvestigations();
            });
    }

    function populateDemoStego() {
        fetch('/api/demo/files/stego')
            .then(res => {
                if (!res.ok) throw new Error('Could not fetch stego carrier artifact');
                return res.blob();
            })
            .then(blob => {
                const file = new File([blob], 'demo_stego_artifact.png', { type: 'image/png' });
                const formData = new FormData();
                formData.append('file', file);
                return fetch('/api/stego/extract', { method: 'POST', body: formData });
            })
            .then(res => res.json())
            .then(data => {
                const box = document.getElementById('extract-result');
                const textOutput = document.getElementById('extracted-text-output');
                if (box) {
                    box.classList.remove('hidden');
                    box.className = 'result-box result-success';
                }
                const secret = data.secret || 'NetSentinel-Demo-Evidence-Token-987';
                if (textOutput) {
                    textOutput.textContent = secret;
                } else if (box) {
                    box.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fa-solid fa-circle-check" style="color: var(--primary-accent);"></i>
                                <strong>Extracted Secret Payload:</strong>
                            </div>
                        </div>
                        <pre id="extracted-text-output">${escapeHtml(secret)}</pre>
                    `;
                }
                if (window.NetSentinelSound) window.NetSentinelSound.play('success');
            })
            .catch(err => {
                const box = document.getElementById('extract-result');
                if (box) {
                    box.classList.remove('hidden');
                    box.innerHTML = `<pre>NetSentinel-Demo-Evidence-Token-987</pre>`;
                }
            });
    }

    function populateDemoImageForensics() {
        fetch('/api/demo/files/stego')
            .then(res => res.blob())
            .then(blob => {
                const file = new File([blob], 'demo_stego_artifact.png', { type: 'image/png' });
                const formData = new FormData();
                formData.append('file', file);
                return fetch('/api/forensics/analyze', { method: 'POST', body: formData });
            })
            .then(res => res.json())
            .then(data => {
                const details = document.getElementById('forensics-details');
                const container = document.getElementById('forensics-results');
                if (container) container.classList.remove('hidden');
                if (details) {
                    details.innerHTML = `
                        <div class="forensics-stat-tile"><strong>Filename</strong>${escapeHtml(data.filename || 'demo_stego_artifact.png')}</div>
                        <div class="forensics-stat-tile"><strong>Format</strong>${escapeHtml(data.format || 'PNG')} (${escapeHtml(data.dimensions || '120x80')})</div>
                        <div class="forensics-stat-tile"><strong>SHA-256</strong><code style="word-break: break-all;">${escapeHtml(data.sha256 || 'N/A')}</code></div>
                        <div class="forensics-stat-tile"><strong>Susposity Score</strong><span class="badge badge-danger">${escapeHtml(data.susposity_score || 88.5)} / 100 &bull; High Risk</span></div>
                        <div class="forensics-indicators-card"><strong>Heuristic Flags</strong><ul><li>Anomalous LSB spatial entropy detected</li><li>Covert steganographic payload signature verified</li></ul></div>
                    `;
                }
                if (window.sileo) window.sileo.warning('Image forensics analyzed demo stego artifact successfully.');
            })
            .catch(() => {});
    }

    function populateDemoIntegrity() {
        fetch('/api/demo/files/baseline_info')
            .then(res => res.json())
            .then(info => {
                const box = document.getElementById('integrity-result');
                if (box) {
                    box.classList.remove('hidden');
                    box.innerHTML = `
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fa-solid fa-triangle-exclamation" style="color: var(--critical);"></i>
                                <span class="badge badge-danger">TAMPER DETECTION VERIFIED (Demo Comparison)</span>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                                <strong>Filename:</strong> ${escapeHtml(info.filename)}<br/>
                                <strong>Clean Reference Hash:</strong> <code style="color: var(--primary-accent);">${escapeHtml(info.clean_hash)}</code><br/>
                                <strong>Tampered Current Hash:</strong> <code style="color: var(--critical);">${escapeHtml(info.tampered_hash)}</code>
                            </div>
                        </div>
                    `;
                }
                // integrity loaded successfully
            })
            .catch(() => {});
    }

    function populateDemoReports() {
        const pdfLink = document.getElementById('demo-download-pdf-btn');
        if (pdfLink) {
            pdfLink.scrollIntoView({ behavior: 'smooth', block: 'center' });
            pdfLink.style.boxShadow = '0 0 16px rgba(183, 243, 107, 0.6)';
            setTimeout(() => {
                pdfLink.style.boxShadow = '';
            }, 2500);
        }
        window.open('/api/demo/report/pdf', '_blank');
        if (window.sileo) window.sileo.success('Consolidated Demo PDF Investigation Report generated and opened.');
    }

    function populateDemoSystemHealth() {
        fetch('/api/demo/health')
            .then(res => res.json())
            .then(h => {
                const cpuVal = document.getElementById('demo-health-cpu');
                const cpuBar = document.getElementById('demo-health-cpu-bar');
                const memVal = document.getElementById('demo-health-mem');
                const memBar = document.getElementById('demo-health-mem-bar');
                const latVal = document.getElementById('demo-health-latency');
                const latBar = document.getElementById('demo-health-latency-bar');
                const rateVal = document.getElementById('demo-health-rate');
                const rateBar = document.getElementById('demo-health-rate-bar');

                const cpu = typeof h.cpu_percent === 'number' ? h.cpu_percent : 24.5;
                const mem = typeof h.memory_percent === 'number' ? h.memory_percent : 38.2;
                const lat = typeof h.latency_ms === 'number' ? h.latency_ms : 12.4;
                const drop = typeof h.packet_drop_rate === 'number' ? (h.packet_drop_rate * 100) : 0.0;

                if (cpuVal) cpuVal.textContent = `${cpu.toFixed(1)}%`;
                if (cpuBar) cpuBar.style.width = `${Math.min(100, Math.max(0, cpu))}%`;

                if (memVal) memVal.textContent = `${mem.toFixed(1)}%`;
                if (memBar) memBar.style.width = `${Math.min(100, Math.max(0, mem))}%`;

                if (latVal) latVal.textContent = `${lat.toFixed(1)} ms`;
                if (latBar) latBar.style.width = `${Math.min(100, (lat / 100) * 100)}%`;

                if (rateVal) rateVal.textContent = `${drop.toFixed(2)}%`;
                if (rateBar) rateBar.style.width = `${Math.min(100, drop * 20)}%`;

                const curState = (h.collector_status || 'LIVE').toUpperCase();
                document.querySelectorAll('.demo-collector-toggle-btn').forEach(btn => {
                    if (btn.getAttribute('data-state') === curState) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });

                if (demoState.openHealthModal) {
                    demoState.openHealthModal();
                }

                if (window.sileo) {
                    window.sileo.info(`System Health Diagnostics [Collector: ${curState}] CPU: ${cpu.toFixed(1)}% | Latency: ${lat.toFixed(1)}ms`);
                }
            })
            .catch(() => {
                if (demoState.openHealthModal) {
                    demoState.openHealthModal();
                }
            });
    }

    function populateDemoForFeature(feature) {
        switch (feature) {
            case 'network_monitor':
                populateDemoNetworkMonitor();
                break;
            case 'analytics':
                populateDemoAnalytics();
                break;
            case 'csv_analysis':
                populateDemoCsvAnalysis();
                break;
            case 'topology':
                populateDemoTopology();
                break;
            case 'devices':
                populateDemoDeviceInventory();
                break;
            case 'flows':
                populateDemoFlowExplorer();
                break;
            case 'threat_intel':
                demoThreatIntel();
                break;
            case 'soc_alerts':
                populateDemoSocAlerts();
                break;
            case 'investigations':
                populateDemoInvestigations();
                break;
            case 'stego':
                populateDemoStego();
                break;
            case 'forensics':
                populateDemoImageForensics();
                break;
            case 'integrity':
                populateDemoIntegrity();
                break;
            case 'reports':
                populateDemoReports();
                break;
            case 'health':
                populateDemoSystemHealth();
                break;
            default:
                populateDemoNetworkMonitor();
                break;
        }
    }

    function demoNetworkMonitor() {
        const viewId = 'overview-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoNetworkMonitor();
    }

    function demoAnalytics() {
        const viewId = 'analytics-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoAnalytics();
    }

    function demoCsvAnalysis() {
        const viewId = 'network-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoCsvAnalysis();
    }

    function demoTopology() {
        const viewId = 'topology-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoTopology();
    }

    function demoDeviceInventory() {
        const viewId = 'devices-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoDeviceInventory();
    }

    function demoFlowExplorer() {
        const viewId = 'live-collector-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoFlowExplorer();
    }

    function demoSocAlerts() {
        const viewId = 'soc-alerts-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoSocAlerts();
    }

    function demoInvestigations() {
        const viewId = 'investigations-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoInvestigations();
    }

    function demoStego() {
        const viewId = 'stego-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoStego();
    }

    function demoImageForensics() {
        const viewId = 'forensics-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoImageForensics();
    }

    function demoIntegrity() {
        const viewId = 'integrity-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoIntegrity();
    }

    function demoReports() {
        const viewId = 'reports-view';
        const panel = document.getElementById(viewId);
        if (panel && !panel.classList.contains('active') && window.switchView) {
            window.switchView(viewId);
        }
        populateDemoReports();
    }

    function demoSystemHealth() {
        populateDemoSystemHealth();
    }

    // ==========================================================================
    // onViewSwitched - Maps view panel IDs to populate functions
    // ==========================================================================
    function onViewSwitched(targetId) {
        switch (targetId) {
            case 'overview-view':
                populateDemoNetworkMonitor();
                break;
            case 'analytics-view':
                populateDemoAnalytics();
                break;
            case 'network-view':
                populateDemoCsvAnalysis();
                break;
            case 'topology-view':
                populateDemoTopology();
                break;
            case 'devices-view':
                populateDemoDeviceInventory();
                break;
            case 'live-collector-view':
                populateDemoFlowExplorer();
                break;
            case 'soc-alerts-view':
                populateDemoSocAlerts();
                break;
            case 'investigations-view':
                populateDemoInvestigations();
                break;
            case 'stego-view':
                populateDemoStego();
                break;
            case 'forensics-view':
                populateDemoImageForensics();
                break;
            case 'integrity-view':
                populateDemoIntegrity();
                break;
            case 'reports-view':
                populateDemoReports();
                break;
            case 'settings-view':
                break;
            default:
                break;
        }
    }

    // Expose global controller on window
    window.NetSentinelDemo = {
        // State getters
        isDemoMode: () => demoState.active,
        getState: () => ({ ...demoState }),
        getStatus: () => demoState.status,

        // View switcher integration
        onViewSwitched: onViewSwitched,

        // Lifecycle
        init: init,
        enable: enable,
        disable: disable,
        reset: reset,

        // Demo controls
        updateBandwidth: updateBandwidth,
        injectAnomaly: injectAnomaly,
        toggleCollectorState: toggleCollectorState,
        inspectDevice: inspectDevice,
        triageDemoAlert: triageDemoAlert,

        // Feature walkthroughs
        demoNetworkMonitor: demoNetworkMonitor,
        demoAnalytics: demoAnalytics,
        demoCsvAnalysis: demoCsvAnalysis,
        demoTopology: demoTopology,
        demoDeviceInventory: demoDeviceInventory,
        demoFlowExplorer: demoFlowExplorer,
        demoThreatIntel: demoThreatIntel,
        demoSocAlerts: demoSocAlerts,
        demoInvestigations: demoInvestigations,
        demoStego: demoStego,
        demoImageForensics: demoImageForensics,
        demoIntegrity: demoIntegrity,
        demoReports: demoReports,
        demoSystemHealth: demoSystemHealth,

        // Separate data population functions (no switchView)
        populateDemoNetworkMonitor: populateDemoNetworkMonitor,
        populateDemoAnalytics: populateDemoAnalytics,
        populateDemoCsvAnalysis: populateDemoCsvAnalysis,
        populateDemoTopology: populateDemoTopology,
        populateDemoDeviceInventory: populateDemoDeviceInventory,
        populateDemoFlowExplorer: populateDemoFlowExplorer,
        populateDemoSocAlerts: populateDemoSocAlerts,
        populateDemoInvestigations: populateDemoInvestigations,
        populateDemoStego: populateDemoStego,
        populateDemoImageForensics: populateDemoImageForensics,
        populateDemoIntegrity: populateDemoIntegrity,
        populateDemoReports: populateDemoReports,
        populateDemoSystemHealth: populateDemoSystemHealth,

        // Function aliases expected by app.js mapped to populateDemo*
        loadDemoOverview: populateDemoNetworkMonitor,
        loadDemoDevices: populateDemoDeviceInventory,
        loadDemoFlows: populateDemoFlowExplorer,
        loadDemoSocAlerts: populateDemoSocAlerts,
        loadDemoTopology: populateDemoTopology,
        loadDemoInvestigations: populateDemoInvestigations
    };

    // Auto-init on DOM content loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window);