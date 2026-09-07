/**
 * U1-OS Cyberpunk Holographic Command Room 3D Engine
 * Interactive 3D particle globe, rotating orbital rings, global node mesh topology,
 * and holographic scanlines. Pure self-contained WebGL / Canvas matrix engine.
 */

(function() {
    let canvas = null;
    let ctx = null;
    let animId = null;
    let isRunning = false;
    let rotationX = 0.2;
    let rotationY = 0.0;
    let targetRotX = 0.2;
    let targetRotY = 0.0;
    let zoom = 1.0;
    let isDragging = false;
    let lastMouseX = 0;
    let lastMouseY = 0;

    // 3D Nodes: Global C2 Points
    const NODES = [
        { name: "Tokyo Jito Hub", lat: 35.6762, lon: 139.6503, ping: 18, color: "#00ffcc" },
        { name: "NY Mempool Node", lat: 40.7128, lon: -74.0060, ping: 24, color: "#00ffcc" },
        { name: "Frankfurt Relay", lat: 50.1109, lon: 8.6821, ping: 12, color: "#a855f7" },
        { name: "London Sovereign", lat: 51.5074, lon: -0.1278, ping: 15, color: "#3b82f6" },
        { name: "Singapore Gateway", lat: 1.3521, lon: 103.8198, ping: 32, color: "#f59e0b" },
        { name: "Sydney C2 Station", lat: -33.8688, lon: 151.2093, ping: 45, color: "#10b981" }
    ];

    // Generate Globe Particles on Sphere Surface
    const PARTICLES = [];
    const NUM_PARTICLES = 360;
    for (let i = 0; i < NUM_PARTICLES; i++) {
        const phi = Math.acos(-1 + (2 * i) / NUM_PARTICLES);
        const theta = Math.sqrt(NUM_PARTICLES * Math.PI) * phi;
        PARTICLES.push({
            x: Math.cos(theta) * Math.sin(phi),
            y: Math.sin(theta) * Math.sin(phi),
            z: Math.cos(phi),
            baseAlpha: 0.3 + Math.random() * 0.5,
            pulse: Math.random() * Math.PI * 2
        });
    }

    function latLonTo3D(lat, lon, radius) {
        const phi = (90 - lat) * (Math.PI / 180);
        const theta = (lon + 180) * (Math.PI / 180);
        return {
            x: -radius * Math.sin(phi) * Math.cos(theta),
            y: radius * Math.cos(phi),
            z: radius * Math.sin(phi) * Math.sin(theta)
        };
    }

    function project3D(x, y, z, cx, cy, fov) {
        // Apply Y and X rotation
        const cosY = Math.cos(rotationY);
        const sinY = Math.sin(rotationY);
        const cosX = Math.cos(rotationX);
        const sinX = Math.sin(rotationX);

        // Rotate around Y
        let x1 = x * cosY + z * sinY;
        let z1 = -x * sinY + z * cosY;

        // Rotate around X
        let y1 = y * cosX - z1 * sinX;
        let z2 = y * sinX + z1 * cosX;

        // Distance & Perspective
        const dist = 320 * zoom;
        const scale = dist / (dist + z2);

        return {
            x: cx + x1 * scale,
            y: cy + y1 * scale,
            scale: scale,
            z: z2
        };
    }

    function initHologram() {
        canvas = document.getElementById("hologramCanvas");
        if (!canvas) return;
        ctx = canvas.getContext("2d");

        function resize() {
            if (!canvas) return;
            canvas.width = canvas.parentElement.clientWidth || 800;
            canvas.height = canvas.parentElement.clientHeight || 560;
        }
        resize();
        window.addEventListener("resize", resize);

        // Mouse Drag Interaction
        canvas.addEventListener("mousedown", (e) => {
            isDragging = true;
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
        });

        window.addEventListener("mousemove", (e) => {
            if (!isDragging) return;
            const dx = e.clientX - lastMouseX;
            const dy = e.clientY - lastMouseY;
            targetRotY += dx * 0.008;
            targetRotX = Math.max(-1.2, Math.min(1.2, targetRotX + dy * 0.008));
            lastMouseX = e.clientX;
            lastMouseY = e.clientY;
        });

        window.addEventListener("mouseup", () => {
            isDragging = false;
        });

        canvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            zoom = Math.max(0.6, Math.min(2.0, zoom - e.deltaY * 0.001));
        }, { passive: false });
    }

    function render(timestamp) {
        if (!isRunning || !ctx || !canvas) return;

        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const baseRadius = Math.min(w, h) * 0.32;

        // Smooth rotation interpolation
        rotationY += (targetRotY - rotationY) * 0.1;
        rotationX += (targetRotX - rotationX) * 0.1;
        targetRotY += 0.003; // Continuous auto-rotation

        // Dark holographic canvas clear
        ctx.fillStyle = "rgba(7, 10, 19, 0.4)";
        ctx.fillRect(0, 0, w, h);

        // Draw outer orbital rings
        ctx.save();
        ctx.strokeStyle = "rgba(0, 255, 204, 0.15)";
        ctx.lineWidth = 1;
        for (let r = 1; r <= 3; r++) {
            ctx.beginPath();
            const ringR = baseRadius * (1.1 + r * 0.18) * zoom;
            ctx.ellipse(cx, cy, ringR, ringR * 0.35, rotationY * 0.2 * (r % 2 ? 1 : -1), 0, Math.PI * 2);
            ctx.stroke();
        }
        ctx.restore();

        // Draw Globe Particles
        for (let i = 0; i < PARTICLES.length; i++) {
            const p = PARTICLES[i];
            const p3 = project3D(p.x * baseRadius, p.y * baseRadius, p.z * baseRadius, cx, cy, 320);

            if (p3.scale > 0) {
                const alpha = (p3.z > 0 ? 0.2 : 0.8) * p.baseAlpha;
                ctx.fillStyle = `rgba(0, 255, 204, ${alpha})`;
                const size = Math.max(1, 2.5 * p3.scale);
                ctx.beginPath();
                ctx.arc(p3.x, p3.y, size, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw Connection Lines between Nodes
        const projectedNodes = [];
        for (let i = 0; i < NODES.length; i++) {
            const n = NODES[i];
            const pos = latLonTo3D(n.lat, n.lon, baseRadius);
            const proj = project3D(pos.x, pos.y, pos.z, cx, cy, 320);
            projectedNodes.push({ ...n, proj: proj });
        }

        ctx.lineWidth = 1.2;
        for (let i = 0; i < projectedNodes.length; i++) {
            for (let j = i + 1; j < projectedNodes.length; j++) {
                const n1 = projectedNodes[i];
                const n2 = projectedNodes[j];
                if (n1.proj.z < 60 && n2.proj.z < 60) {
                    const grad = ctx.createLinearGradient(n1.proj.x, n1.proj.y, n2.proj.x, n2.proj.y);
                    grad.addColorStop(0, "rgba(0, 255, 204, 0.4)");
                    grad.addColorStop(1, "rgba(168, 85, 247, 0.4)");
                    ctx.strokeStyle = grad;
                    ctx.beginPath();
                    ctx.moveTo(n1.proj.x, n1.proj.y);
                    ctx.lineTo(n2.proj.x, n2.proj.y);
                    ctx.stroke();
                }
            }
        }

        // Draw Interactive Node Beacons
        for (let i = 0; i < projectedNodes.length; i++) {
            const n = projectedNodes[i];
            const p = n.proj;
            if (p.z < 80) {
                // Outer Pulse Ring
                const pulseR = (6 + Math.sin(timestamp * 0.005 + i) * 3) * p.scale;
                ctx.strokeStyle = n.color;
                ctx.beginPath();
                ctx.arc(p.x, p.y, Math.max(2, pulseR), 0, Math.PI * 2);
                ctx.stroke();

                // Center Beacon
                ctx.fillStyle = "#ffffff";
                ctx.beginPath();
                ctx.arc(p.x, p.y, Math.max(2, 3.5 * p.scale), 0, Math.PI * 2);
                ctx.fill();

                // Holographic Label
                ctx.fillStyle = n.color;
                ctx.font = "10px monospace";
                ctx.fillText(`${n.name} (${n.ping}ms)`, p.x + 8, p.y - 6);
            }
        }

        // Draw Scanlines Effect
        ctx.fillStyle = "rgba(0, 255, 204, 0.02)";
        for (let y = 0; y < h; y += 4) {
            ctx.fillRect(0, y, w, 1);
        }

        animId = requestAnimationFrame(render);
    }

    window.openHologramRoom = function() {
        const modal = document.getElementById("hologramModal");
        if (!modal) return;
        modal.style.display = "flex";
        if (!canvas) initHologram();
        isRunning = true;
        animId = requestAnimationFrame(render);
    };

    window.closeHologramRoom = function() {
        const modal = document.getElementById("hologramModal");
        if (modal) modal.style.display = "none";
        isRunning = false;
        if (animId) cancelAnimationFrame(animId);
    };

    document.addEventListener("DOMContentLoaded", () => {
        const btnOpen = document.getElementById("btnHologramView");
        if (btnOpen) {
            btnOpen.addEventListener("click", window.openHologramRoom);
        }
        const btnClose = document.getElementById("btnCloseHologram");
        if (btnClose) {
            btnClose.addEventListener("click", window.closeHologramRoom);
        }
    });
})();
