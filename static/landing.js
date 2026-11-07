/**
 * Net Sentinel — SIGNAL / EVIDENCE
 * Digital Intelligence Laboratory — Network Canvas Controller
 */

(function () {
    "use strict";

    var toggle = document.getElementById("menu-toggle");
    var drawer = document.getElementById("mobile-drawer");

    function closeDrawer() {
        if (!drawer || !toggle) return;
        drawer.hidden = true;
        drawer.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open menu");
    }

    function openDrawer() {
        drawer.hidden = false;
        drawer.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        toggle.setAttribute("aria-label", "Close menu");
    }

    if (toggle && drawer) {
        toggle.addEventListener("click", function () {
            if (toggle.getAttribute("aria-expanded") === "true") closeDrawer();
            else openDrawer();
        });
        drawer.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", closeDrawer);
        });
    }

    var canvas = document.getElementById("network-canvas");
    if (!canvas || !canvas.getContext) return;

    var ctx = canvas.getContext("2d");
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var dpr = 1;
    var width = 0;
    var height = 0;
    var mouse = { x: -9999, y: -9999 };
    var nodes = [];
    var edges = [];
    var particles = [];
    var events = [];
    var rafId = 0;

    var labels = ["GATEWAY-01", "INGRESS-SENSOR", "NEURAL-ANALYST", "DMZ-ROUTER", "FORENSIC-HOST"];
    var badges = ["SIGNAL VERIFIED", "ANOMALY ISOLATED", "SHA-256 HASH MATCH", "LSB STEGO DETECTED"];

    function rand(min, max) {
        return min + Math.random() * (max - min);
    }

    function resizeCanvas() {
        var rect = canvas.getBoundingClientRect();
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = Math.max(1, rect.width);
        height = Math.max(1, rect.height);
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function resize() {
        resizeCanvas();
        buildGraph();
    }

    function initParticles() {
        particles = [];
        if (!reduced) {
            var pCount = Math.min(edges.length, 16);
            for (var p = 0; p < pCount; p++) {
                particles.push({
                    edge: p % edges.length,
                    t: rand(0, 1),
                    speed: rand(0.0018, 0.0036)
                });
            }
        }
    }

    function buildGraph() {
        var count = width < 520 ? 14 : 22;
        nodes = [];
        var roles = ["gateway", "analysis", "sensor", "anomaly", "server", "endpoint"];
        for (var i = 0; i < count; i++) {
            var role = (i === 3 || i === 9) ? "anomaly" : roles[i % roles.length];
            nodes.push({
                x: rand(width * 0.08, width * 0.92),
                y: rand(height * 0.10, height * 0.90),
                bx: 0,
                by: 0,
                r: role === "gateway" ? 6.5 : role === "anomaly" ? 6.0 : role === "analysis" ? 5.5 : 4.0,
                role: role,
                label: labels[i % labels.length],
                phase: rand(0, Math.PI * 2)
            });
            nodes[i].bx = nodes[i].x;
            nodes[i].by = nodes[i].y;
        }

        edges = [];
        for (var n = 1; n < nodes.length; n++) {
            var nearest = 0;
            var best = Infinity;
            for (var m = 0; m < n; m++) {
                var dx = nodes[n].x - nodes[m].x;
                var dy = nodes[n].y - nodes[m].y;
                var dist = dx * dx + dy * dy;
                if (dist < best) {
                    best = dist;
                    nearest = m;
                }
            }
            edges.push({ a: n, b: nearest, pulse: rand(0, 1) });
            if (n % 4 === 0 && n > 2) {
                edges.push({ a: n, b: (nearest + 2) % n, pulse: rand(0, 1) });
            }
        }

        initParticles();
        events = [];
    }

    function spawnEvent() {
        if (!edges.length) return;
        var edge = edges[Math.floor(Math.random() * edges.length)];
        events.push({
            edge: edges.indexOf(edge),
            text: badges[Math.floor(Math.random() * badges.length)],
            life: 1
        });
        if (events.length > 2) events.shift();
    }

    function drawGrid() {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 0.6;
        var gridSize = 40;
        for (var x = 0; x < width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (var y = 0; y < height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }
    }

    function drawFrame(time) {
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "#0A0A0C"; // Background Canvas
        ctx.fillRect(0, 0, width, height);

        drawGrid();

        var t = reduced ? 0 : time * 0.001;

        // Draw connections
        edges.forEach(function (edge, index) {
            var a = nodes[edge.a];
            var b = nodes[edge.b];
            var isAnomaly = a.role === "anomaly" || b.role === "anomaly";
            var hot = events.some(function (ev) { return ev.edge === index && ev.life > 0.15; });
            var pulse = reduced ? 0.35 : 0.22 + 0.18 * (0.5 + 0.5 * Math.sin(t * 1.8 + edge.pulse * 5));

            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);

            if (isAnomaly) {
                ctx.strokeStyle = "rgba(239, 68, 68, 0.85)"; // Critical Red
                ctx.lineWidth = 1.4;
            } else if (hot) {
                ctx.strokeStyle = "rgba(245, 158, 11, 0.85)"; // Alert Amber
                ctx.lineWidth = 1.4;
            } else {
                ctx.strokeStyle = "rgba(6, 182, 212, " + pulse + ")"; // Intelligence Cyan
                ctx.lineWidth = 0.9;
            }
            ctx.stroke();
        });

        // Draw particles traveling along edges
        if (!reduced) {
            particles.forEach(function (particle) {
                particle.t += particle.speed;
                if (particle.t > 1) particle.t = 0;
                var edge = edges[particle.edge];
                if (!edge) return;
                var a = nodes[edge.a];
                var b = nodes[edge.b];
                var isAnomaly = a.role === "anomaly" || b.role === "anomaly";
                var x = a.x + (b.x - a.x) * particle.t;
                var y = a.y + (b.y - a.y) * particle.t;

                ctx.beginPath();
                ctx.arc(x, y, 2.0, 0, Math.PI * 2);
                ctx.fillStyle = isAnomaly ? "#EF4444" : "#06B6D4";
                ctx.fill();
            });
        }

        // Draw nodes
        nodes.forEach(function (node) {
            if (!reduced) {
                var dx = mouse.x - node.x;
                var dy = mouse.y - node.y;
                var dist = Math.hypot(dx, dy);
                if (dist < 100 && dist > 0.01) {
                    node.x += dx * 0.015;
                    node.y += dy * 0.015;
                } else {
                    node.x += (node.bx - node.x) * 0.035;
                    node.y += (node.by - node.y) * 0.035;
                }
            }

            var isAnomaly = node.role === "anomaly";

            // Subtle outer halo
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.r + 3.5, 0, Math.PI * 2);
            ctx.fillStyle = isAnomaly ? "rgba(239, 68, 68, 0.18)" : "rgba(6, 182, 212, 0.14)";
            ctx.fill();

            // Inner core node
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
            ctx.fillStyle = isAnomaly ? "#EF4444" : (node.role === "gateway" ? "#10B981" : "#06B6D4");
            ctx.fill();

            // Border
            ctx.lineWidth = 1;
            ctx.strokeStyle = isAnomaly ? "#EF4444" : "#06B6D4";
            ctx.stroke();

            // Technical label
            if (node.r > 5.0 && width > 480) {
                ctx.fillStyle = "rgba(148, 163, 184, 0.85)";
                ctx.font = "9px 'JetBrains Mono', monospace";
                ctx.fillText(node.label, node.x + 8, node.y + 3);
            }
        });

        // Event text tags
        events.forEach(function (ev) {
            var edge = edges[ev.edge];
            if (!edge) return;
            var a = nodes[edge.a];
            var b = nodes[edge.b];
            var mx = (a.x + b.x) * 0.5;
            var my = (a.y + b.y) * 0.5 - (1 - ev.life) * 14;

            ctx.save();
            ctx.fillStyle = "rgba(18, 19, 22, 0.95)"; // Container / Card Surface
            ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
            ctx.lineWidth = 1;
            ctx.font = "10px 'JetBrains Mono', monospace";
            var textW = ctx.measureText(ev.text).width;
            ctx.fillRect(mx - textW / 2 - 6, my - 9, textW + 12, 18);
            ctx.strokeRect(mx - textW / 2 - 6, my - 9, textW + 12, 18);

            ctx.fillStyle = "#06B6D4";
            ctx.fillText(ev.text, mx - textW / 2, my + 3);
            ctx.restore();

            ev.life -= 0.007;
        });
        events = events.filter(function (ev) { return ev.life > 0; });

        if (!reduced) {
            rafId = requestAnimationFrame(drawFrame);
        }
    }

    canvas.addEventListener("mousemove", function (e) {
        var rect = canvas.getBoundingClientRect();
        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;
    });

    canvas.addEventListener("mouseleave", function () {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    window.addEventListener("resize", resize);

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                if (!rafId && !reduced) {
                    rafId = requestAnimationFrame(drawFrame);
                }
            } else {
                if (rafId) {
                    cancelAnimationFrame(rafId);
                    rafId = 0;
                }
            }
        });
    }, { threshold: 0.1 });

    observer.observe(canvas);
    resize();
    drawFrame(performance.now());
    setInterval(spawnEvent, 4000);
})();
