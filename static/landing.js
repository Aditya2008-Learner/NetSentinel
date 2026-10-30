(function () {
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
    let reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var dpr = 1;
    var width = 0;
    var height = 0;
    var mouse = { x: -9999, y: -9999 };
    var nodes = [];
    var edges = [];
    var particles = [];
    var events = [];
    let rafId = 0;

    var labels = ["GATEWAY", "SENSOR", "ANALYSIS", "SERVER", "ENDPOINT"];
    var badges = ["FLOW OK", "PORT SCAN BLOCKED", "SHA-256 VERIFIED"];

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
            var pCount = Math.min(edges.length, 14);
            for (var p = 0; p < pCount; p++) {
                particles.push({
                    edge: p % edges.length,
                    t: rand(0, 1),
                    speed: rand(0.0016, 0.0034)
                });
            }
        }
    }

    function buildGraph() {
        var count = width < 520 ? 16 : 20;
        nodes = [];
        var roles = ["gateway", "analysis", "sensor", "server", "sensor", "endpoint"];
        for (var i = 0; i < count; i++) {
            var role = roles[i % roles.length];
            nodes.push({
                x: rand(width * 0.1, width * 0.9),
                y: rand(height * 0.12, height * 0.88),
                bx: 0,
                by: 0,
                r: role === "gateway" ? 7 : role === "analysis" ? 6 : 4.5,
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
            if (n % 3 === 0 && n > 2) {
                edges.push({ a: n, b: (nearest + 3) % n, pulse: rand(0, 1) });
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

    function drawFrame(time) {
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "#090d1a";
        ctx.fillRect(0, 0, width, height);

        var t = reduced ? 0 : time * 0.001;

        edges.forEach(function (edge, index) {
            var a = nodes[edge.a];
            var b = nodes[edge.b];
            var hot = events.some(function (ev) { return ev.edge === index && ev.life > 0.15; });
            var pulse = reduced ? 0.45 : 0.28 + 0.22 * (0.5 + 0.5 * Math.sin(t * 1.6 + edge.pulse * 6));
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = hot ? "rgba(245, 158, 11, 0.75)" : "rgba(34, 197, 94, " + pulse + ")";
            ctx.lineWidth = hot ? 1.6 : 1;
            ctx.stroke();
        });

        if (!reduced) {
            particles.forEach(function (particle) {
                particle.t += particle.speed;
                if (particle.t > 1) particle.t = 0;
                var edge = edges[particle.edge];
                if (!edge) return;
                var a = nodes[edge.a];
                var b = nodes[edge.b];
                var x = a.x + (b.x - a.x) * particle.t;
                var y = a.y + (b.y - a.y) * particle.t;
                ctx.beginPath();
                ctx.arc(x, y, 2.1, 0, Math.PI * 2);
                ctx.fillStyle = "#38bdf8";
                ctx.fill();
            });
        }

        nodes.forEach(function (node) {
            if (!reduced) {
                var dx = mouse.x - node.x;
                var dy = mouse.y - node.y;
                var dist = Math.hypot(dx, dy);
                if (dist < 90 && dist > 0.01) {
                    node.x += dx * 0.012;
                    node.y += dy * 0.012;
                } else {
                    node.x += (node.bx - node.x) * 0.04;
                    node.y += (node.by - node.y) * 0.04;
                }
            }
            var alerted = events.some(function (ev) {
                var edge = edges[ev.edge];
                return edge && ev.life > 0.2 && (edge.a === nodes.indexOf(node) || edge.b === nodes.indexOf(node));
            });
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
            ctx.fillStyle = alerted ? "#f59e0b" : (node.role === "gateway" ? "#22c55e" : "#10b981");
            ctx.fill();
            ctx.lineWidth = 4;
            ctx.strokeStyle = alerted ? "rgba(245, 158, 11, 0.25)" : "rgba(16, 185, 129, 0.18)";
            ctx.stroke();
        });

        events.forEach(function (ev) {
            var edge = edges[ev.edge];
            if (!edge) return;
            var a = nodes[edge.a];
            var b = nodes[edge.b];
            var x = (a.x + b.x) / 2;
            var y = (b.y + a.y) / 2 - 14;
            ctx.font = "500 11px JetBrains Mono, ui-monospace, monospace";
            var pad = 6;
            var w = ctx.measureText(ev.text).width + pad * 2;
            ctx.fillStyle = "rgba(9, 13, 26, 0.92)";
            ctx.strokeStyle = ev.text.indexOf("BLOCKED") >= 0 ? "rgba(245, 158, 11, 0.7)" : "rgba(34, 197, 94, 0.7)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            if (typeof ctx.roundRect === "function") {
                ctx.roundRect(x - w / 2, y - 14, w, 18, 4);
            } else {
                ctx.rect(x - w / 2, y - 14, w, 18);
            }
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = ev.text.indexOf("BLOCKED") >= 0 ? "#f59e0b" : "#22c55e";
            ctx.fillText(ev.text, x - w / 2 + pad, y);
            if (!reduced) ev.life -= 0.004;
        });
        events = events.filter(function (ev) { return ev.life > 0; });

        if (!reduced) rafId = window.requestAnimationFrame(animate);
    }

    function animate(time) {
        drawFrame(time);
    }

    canvas.addEventListener("pointermove", function (event) {
        var rect = canvas.getBoundingClientRect();
        mouse.x = event.clientX - rect.left;
        mouse.y = event.clientY - rect.top;
    });
    canvas.addEventListener("pointerleave", function () {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    let resizeTimeout;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            resizeCanvas();
            buildGraph();
            if (reduced) drawFrame(0);
        }, 150);
    });

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    motionQuery.addEventListener("change", (e) => {
        reduced = e.matches;
        if (reduced) {
            particles = [];
            if (rafId) cancelAnimationFrame(rafId);
            drawFrame(0);
        } else {
            initParticles();
            rafId = requestAnimationFrame(animate);
        }
    });

    resize();
    drawFrame(0);
    if (!reduced) {
        window.setInterval(spawnEvent, 4200);
    }
})();
