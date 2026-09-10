/**
 * AURA-TRAFFIC AI // Enterprise Operations Center Logic
 * High-definition 2D arterial corridor simulator, AI Text-to-SQL copilot, and telemetry synchronizer.
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // DOM Selectors
    // -------------------------------------------------------------
    const canvas = document.getElementById('trafficCanvas');
    const ctx = canvas.getContext('2d');

    // Header & Badges
    const badgeSimState = document.getElementById('badgeSimState');
    const labelSimStep = document.getElementById('labelSimStep');
    const labelDbEngine = document.getElementById('labelDbEngine');
    const labelAiEngine = document.getElementById('labelAiEngine');
    const badgeEmergency = document.getElementById('badgeEmergency');
    const clockUtc = document.getElementById('clockUtc');
    const auditTicker = document.getElementById('auditTicker');

    // KPIs
    const kpiThroughput = document.getElementById('kpiThroughput');
    const kpiWaitTime = document.getElementById('kpiWaitTime');
    const kpiQueue = document.getElementById('kpiQueue');
    const kpiAvgSpeed = document.getElementById('kpiAvgSpeed');

    // AI Terminal
    const terminalInput = document.getElementById('terminalInput');
    const btnSendQuery = document.getElementById('btnSendQuery');
    const safetyStatusPill = document.getElementById('safetyStatusPill');
    const perfLatency = document.getElementById('perfLatency');
    const aiNarrativeText = document.getElementById('aiNarrativeText');
    const countTableRows = document.getElementById('countTableRows');
    const tableContainer = document.getElementById('tableContainer');
    const sqlCodeBlock = document.getElementById('sqlCodeBlock');
    const btnCopySql = document.getElementById('btnCopySql');
    const btnExportCsv = document.getElementById('btnExportCsv');

    // Tabs
    const tabBtns = document.querySelectorAll('.terminal-tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Controls & Nodes
    const btnAmbulance = document.getElementById('btnAmbulance');
    const btnFireRescue = document.getElementById('btnFireRescue');
    const btnToggleSim = document.getElementById('btnToggleSim');
    const labelSimBtn = document.getElementById('labelSimBtn');
    const iconSimPlay = document.getElementById('iconSimPlay');
    const btnResetView = document.getElementById('btnResetView');
    const nodesGrid = document.getElementById('nodesGrid');

    // State Variables
    let currentTelemetry = null;
    let vehicles = [];
    let currentQueryResult = null;
    let selectedNodeId = null;

    // -------------------------------------------------------------
    // Live Clock
    // -------------------------------------------------------------
    function updateClock() {
        const now = new Date();
        clockUtc.innerText = now.toUTCString().slice(17, 25) + ' UTC';
    }
    setInterval(updateClock, 1000);
    updateClock();

    // -------------------------------------------------------------
    // Canvas Sizing & Vehicle Physics
    // -------------------------------------------------------------
    function resizeCanvas() {
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function initVehicles() {
        vehicles = [];
        const colors = ['#38bdf8', '#818cf8', '#cbd5e1', '#38bdf8', '#94a3b8', '#67e8f9'];
        const w = canvas.width || 800;
        const h = canvas.height || 400;

        // East-West vehicles (Eastbound and Westbound)
        for (let i = 0; i < 16; i++) {
            const isEastbound = (i % 2 === 0);
            vehicles.push({
                id: 'ew_' + i,
                isEW: true,
                nodeId: null,
                laneOffset: isEastbound ? 16 : -16, // Eastbound (+x) or Westbound (-x)
                x: (w / 16) * i,
                y: (h * 0.5) + (isEastbound ? 16 : -16),
                speed: 0.8 + Math.random() * 0.8,
                maxSpeed: 1.4 + Math.random() * 0.6,
                length: 18 + Math.floor(Math.random() * 6),
                width: 10,
                color: colors[i % colors.length]
            });
        }

        // North-South vehicles at Node 2 (1st Ave)
        for (let i = 0; i < 8; i++) {
            const isSouthbound = (i % 2 === 0);
            vehicles.push({
                id: 'ns2_' + i,
                isEW: false,
                nodeId: 'Node2',
                laneOffset: isSouthbound ? 16 : -16, // Southbound (+y) or Northbound (-y)
                x: (w * 0.32) + (isSouthbound ? 16 : -16),
                y: (h / 8) * i,
                speed: 0.8 + Math.random() * 0.8,
                maxSpeed: 1.3 + Math.random() * 0.5,
                length: 18 + Math.floor(Math.random() * 6),
                width: 10,
                color: colors[(i + 2) % colors.length]
            });
        }

        // North-South vehicles at Node 5 (4th Ave)
        for (let i = 0; i < 8; i++) {
            const isSouthbound = (i % 2 === 0);
            vehicles.push({
                id: 'ns5_' + i,
                isEW: false,
                nodeId: 'Node5',
                laneOffset: isSouthbound ? 16 : -16,
                x: (w * 0.68) + (isSouthbound ? 16 : -16),
                y: (h / 8) * i,
                speed: 0.8 + Math.random() * 0.8,
                maxSpeed: 1.3 + Math.random() * 0.5,
                length: 18 + Math.floor(Math.random() * 6),
                width: 10,
                color: colors[(i + 4) % colors.length]
            });
        }
    }
    initVehicles();

    if (btnResetView) {
        btnResetView.addEventListener('click', () => {
            initVehicles();
            selectedNodeId = null;
        });
    }

    // -------------------------------------------------------------
    // High-Definition Canvas Rendering & Traffic Physics
    // -------------------------------------------------------------
    function renderCanvas() {
        const w = canvas.width;
        const h = canvas.height;
        const centerY = h * 0.5;
        const roadW = 76;
        const node2X = w * 0.32;
        const node5X = w * 0.68;

        // Background / Terrain
        ctx.fillStyle = '#070a13';
        ctx.fillRect(0, 0, w, h);

        // Grid lines (subtle CAD styling)
        ctx.strokeStyle = 'rgba(30, 41, 59, 0.3)';
        ctx.lineWidth = 1;
        for (let x = 0; x < w; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
            ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }

        // 1. Draw Asphalt Roads
        ctx.fillStyle = '#111827';
        // Main EW Arterial (Main Street)
        ctx.fillRect(0, centerY - roadW / 2, w, roadW);
        // NS Avenues (1st Ave @ Node2 & 4th Ave @ Node5)
        ctx.fillRect(node2X - roadW / 2, 0, roadW, h);
        ctx.fillRect(node5X - roadW / 2, 0, roadW, h);

        // Road Curbs / Borders
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 2;
        ctx.strokeRect(0, centerY - roadW / 2, w, roadW);
        ctx.strokeRect(node2X - roadW / 2, 0, roadW, h);
        ctx.strokeRect(node5X - roadW / 2, 0, roadW, h);

        // Center Dividers (Double Amber)
        ctx.strokeStyle = '#d97706';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        // EW Divider
        ctx.moveTo(0, centerY - 1); ctx.lineTo(w, centerY - 1);
        ctx.moveTo(0, centerY + 1); ctx.lineTo(w, centerY + 1);
        // NS Dividers
        ctx.moveTo(node2X - 1, 0); ctx.lineTo(node2X - 1, h);
        ctx.moveTo(node2X + 1, 0); ctx.lineTo(node2X + 1, h);
        ctx.moveTo(node5X - 1, 0); ctx.lineTo(node5X - 1, h);
        ctx.moveTo(node5X + 1, 0); ctx.lineTo(node5X + 1, h);
        ctx.stroke();

        // Dashed Lane Guides
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
        ctx.setLineDash([8, 8]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        // EW lane dashes
        ctx.moveTo(0, centerY - roadW / 4); ctx.lineTo(w, centerY - roadW / 4);
        ctx.moveTo(0, centerY + roadW / 4); ctx.lineTo(w, centerY + roadW / 4);
        ctx.stroke();
        ctx.setLineDash([]);

        // Zebra Pedestrian Crosswalks & Solid White Stop Lines
        function drawCrosswalkAndStopLine(cx, cy) {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.12)';
            const pad = roadW / 2 + 8;
            // Zebra Crosswalks
            for (let i = -roadW / 2 + 4; i < roadW / 2 - 4; i += 8) {
                ctx.fillRect(cx + i, cy - pad - 8, 4, 8);
                ctx.fillRect(cx + i, cy + pad, 4, 8);
                ctx.fillRect(cx - pad - 8, cy + i, 8, 4);
                ctx.fillRect(cx + pad, cy + i, 8, 4);
            }

            // Solid White Stop Lines (where vehicles stop when red)
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 3;
            ctx.beginPath();
            // West approach stop line (Eastbound)
            ctx.moveTo(cx - pad - 8, cy); ctx.lineTo(cx - pad - 8, cy + roadW / 2);
            // East approach stop line (Westbound)
            ctx.moveTo(cx + pad + 8, cy - roadW / 2); ctx.lineTo(cx + pad + 8, cy);
            // North approach stop line (Southbound)
            ctx.moveTo(cx, cy - pad - 8); ctx.lineTo(cx + roadW / 2, cy - pad - 8);
            // South approach stop line (Northbound)
            ctx.moveTo(cx - roadW / 2, cy + pad + 8); ctx.lineTo(cx, cy + pad + 8);
            ctx.stroke();
        }
        drawCrosswalkAndStopLine(node2X, centerY);
        drawCrosswalkAndStopLine(node5X, centerY);

        // Emergency Corridor Highlight Wave
        const hasEmergency = currentTelemetry && currentTelemetry.emergency_count > 0;
        if (hasEmergency) {
            const timeVal = Date.now() / 300;
            const waveAlpha = 0.2 + 0.15 * Math.sin(timeVal);

            // Glowing Green Wave Beam along EW corridor
            const grad = ctx.createLinearGradient(0, centerY, w, centerY);
            grad.addColorStop(0, `rgba(16, 185, 129, ${waveAlpha})`);
            grad.addColorStop(0.5, `rgba(6, 182, 212, ${waveAlpha * 1.5})`);
            grad.addColorStop(1, `rgba(16, 185, 129, ${waveAlpha})`);

            ctx.fillStyle = grad;
            ctx.fillRect(0, centerY - roadW / 2, w, roadW);

            // Corridor Lock Text Banner
            ctx.fillStyle = '#10b981';
            ctx.font = '600 11px "JetBrains Mono", monospace';
            ctx.fillText('⚡ PREEMPTIVE GREEN CORRIDOR LOCKED: NODE 2 ➔ NODE 5', 20, centerY - roadW / 2 - 12);
        }

        // Telemetry Node Data
        const node2 = currentTelemetry && currentTelemetry.intersections ? currentTelemetry.intersections.find(n => n.id === 'Node2') : null;
        const node5 = currentTelemetry && currentTelemetry.intersections ? currentTelemetry.intersections.find(n => n.id === 'Node5') : null;

        // 2. Intersection Controllers & High-Resolution Signal Heads
        function drawSignalNode(x, y, nodeId, title, nodeData) {
            const isSelected = (selectedNodeId === nodeId);
            // Phases: 0 = EW Green, 1 = EW Yellow, 2 = NS Green, 3 = NS Yellow
            const phase = nodeData ? nodeData.current_phase : 0;
            const isEWGreen = (phase === 0);
            const isEWYel = (phase === 1);
            const isNSGreen = (phase === 2);
            const isNSYel = (phase === 3);

            // Intersection Core Box
            ctx.fillStyle = isSelected ? 'rgba(56, 189, 248, 0.15)' : '#0f172a';
            ctx.fillRect(x - roadW / 2, y - roadW / 2, roadW, roadW);
            ctx.strokeStyle = isSelected ? '#38bdf8' : (nodeData && nodeData.emergency_override) ? '#10b981' : '#334155';
            ctx.lineWidth = isSelected ? 2 : 1.5;
            ctx.strokeRect(x - roadW / 2, y - roadW / 2, roadW, roadW);

            // Node ID & Title
            ctx.fillStyle = isSelected ? '#38bdf8' : '#f8fafc';
            ctx.font = '600 11px "Inter", sans-serif';
            ctx.fillText(nodeId, x - 18, y - roadW / 2 - 16);

            // EW Signal Post (East side)
            ctx.fillStyle = '#090d16';
            ctx.fillRect(x + roadW / 2 + 4, y - 16, 10, 32);
            ctx.strokeStyle = '#334155';
            ctx.strokeRect(x + roadW / 2 + 4, y - 16, 10, 32);

            // EW Red, Yellow, Green LED lamps
            const isEWRedActive = (!isEWGreen && !isEWYel);
            ctx.fillStyle = isEWRedActive ? '#ef4444' : 'rgba(239, 68, 68, 0.2)';
            ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y - 10, 3, 0, Math.PI * 2); ctx.fill();
            if (isEWRedActive) {
                ctx.fillStyle = 'rgba(239, 68, 68, 0.35)';
                ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y - 10, 6, 0, Math.PI * 2); ctx.fill();
            }

            ctx.fillStyle = isEWYel ? '#f59e0b' : 'rgba(245, 158, 11, 0.2)';
            ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y, 3, 0, Math.PI * 2); ctx.fill();
            if (isEWYel) {
                ctx.fillStyle = 'rgba(245, 158, 11, 0.35)';
                ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y, 6, 0, Math.PI * 2); ctx.fill();
            }

            ctx.fillStyle = isEWGreen ? '#10b981' : 'rgba(16, 185, 129, 0.2)';
            ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y + 10, 3, 0, Math.PI * 2); ctx.fill();
            if (isEWGreen) {
                ctx.fillStyle = 'rgba(16, 185, 129, 0.35)';
                ctx.beginPath(); ctx.arc(x + roadW / 2 + 9, y + 10, 6, 0, Math.PI * 2); ctx.fill();
            }

            // NS Signal Post (North side)
            ctx.fillStyle = '#090d16';
            ctx.fillRect(x - 16, y - roadW / 2 - 14, 32, 10);
            ctx.strokeStyle = '#334155';
            ctx.strokeRect(x - 16, y - roadW / 2 - 14, 32, 10);

            // NS Red, Yellow, Green LED lamps
            const isNSRedActive = (!isNSGreen && !isNSYel);
            ctx.fillStyle = isNSRedActive ? '#ef4444' : 'rgba(239, 68, 68, 0.2)';
            ctx.beginPath(); ctx.arc(x - 10, y - roadW / 2 - 9, 3, 0, Math.PI * 2); ctx.fill();
            if (isNSRedActive) {
                ctx.fillStyle = 'rgba(239, 68, 68, 0.35)';
                ctx.beginPath(); ctx.arc(x - 10, y - roadW / 2 - 9, 6, 0, Math.PI * 2); ctx.fill();
            }

            ctx.fillStyle = isNSYel ? '#f59e0b' : 'rgba(245, 158, 11, 0.2)';
            ctx.beginPath(); ctx.arc(x, y - roadW / 2 - 9, 3, 0, Math.PI * 2); ctx.fill();
            if (isNSYel) {
                ctx.fillStyle = 'rgba(245, 158, 11, 0.35)';
                ctx.beginPath(); ctx.arc(x, y - roadW / 2 - 9, 6, 0, Math.PI * 2); ctx.fill();
            }

            ctx.fillStyle = isNSGreen ? '#10b981' : 'rgba(16, 185, 129, 0.2)';
            ctx.beginPath(); ctx.arc(x + 10, y - roadW / 2 - 9, 3, 0, Math.PI * 2); ctx.fill();
            if (isNSGreen) {
                ctx.fillStyle = 'rgba(16, 185, 129, 0.35)';
                ctx.beginPath(); ctx.arc(x + 10, y - roadW / 2 - 9, 6, 0, Math.PI * 2); ctx.fill();
            }
        }

        drawSignalNode(node2X, centerY, 'Node 2', 'Downtown West', node2);
        drawSignalNode(node5X, centerY, 'Node 5', 'Downtown East', node5);

        // -------------------------------------------------------------
        // 3. Traffic Physics: Red Light Stopping & Queue Accumulation
        // -------------------------------------------------------------
        // Stop Line Boundaries
        const stopPad = roadW / 2 + 16;
        const stopLineN2_Eastbound = node2X - stopPad;
        const stopLineN2_Westbound = node2X + stopPad;
        const stopLineN5_Eastbound = node5X - stopPad;
        const stopLineN5_Westbound = node5X + stopPad;

        const stopLine_Southbound = centerY - stopPad;
        const stopLine_Northbound = centerY + stopPad;

        // Current Signal States
        // Node 2: phase 0 is EW Green, phase 2 is NS Green
        const isNode2_EW_Red = node2 ? (node2.current_phase !== 0) : false;
        const isNode2_NS_Red = node2 ? (node2.current_phase !== 2) : true;

        // Node 5:
        const isNode5_EW_Red = node5 ? (node5.current_phase !== 0) : false;
        const isNode5_NS_Red = node5 ? (node5.current_phase !== 2) : true;

        // Process each vehicle
        vehicles.forEach((v, idx) => {
            let targetSpeed = v.maxSpeed;
            let shouldStop = false;

            if (v.isEW) {
                const laneY = centerY + v.laneOffset;
                const isEastbound = (v.laneOffset > 0);

                if (isEastbound) {
                    // Moving Right (+x)
                    // Check upcoming intersection
                    if (v.x < stopLineN2_Eastbound && (stopLineN2_Eastbound - v.x) < 140) {
                        if (isNode2_EW_Red) {
                            // Red light at Node 2!
                            if (v.x >= stopLineN2_Eastbound - 16) {
                                shouldStop = true;
                                v.x = Math.min(v.x, stopLineN2_Eastbound - 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (stopLineN2_Eastbound - v.x) * 0.04);
                            }
                        }
                    } else if (v.x > node2X && v.x < stopLineN5_Eastbound && (stopLineN5_Eastbound - v.x) < 140) {
                        if (isNode5_EW_Red) {
                            // Red light at Node 5!
                            if (v.x >= stopLineN5_Eastbound - 16) {
                                shouldStop = true;
                                v.x = Math.min(v.x, stopLineN5_Eastbound - 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (stopLineN5_Eastbound - v.x) * 0.04);
                            }
                        }
                    }

                    // Car-following: don't crash into vehicle ahead in same lane!
                    vehicles.forEach((other, oIdx) => {
                        if (idx !== oIdx && other.isEW && other.laneOffset === v.laneOffset) {
                            const gap = other.x - v.x;
                            if (gap > 0 && gap < 28) {
                                shouldStop = true;
                                targetSpeed = Math.min(targetSpeed, other.speed * 0.5);
                                if (gap < 20) {
                                    v.x = other.x - 20;
                                }
                            }
                        }
                    });

                    // Update speed smoothly
                    if (shouldStop) {
                        v.speed = Math.max(0, v.speed - 0.15);
                    } else {
                        v.speed = Math.min(targetSpeed, v.speed + 0.08);
                    }

                    v.x += v.speed;
                    if (v.x > w + 40) v.x = -30;

                } else {
                    // Moving Left (-x)
                    // Check upcoming intersection
                    if (v.x > stopLineN5_Westbound && (v.x - stopLineN5_Westbound) < 140) {
                        if (isNode5_EW_Red) {
                            if (v.x <= stopLineN5_Westbound + 16) {
                                shouldStop = true;
                                v.x = Math.max(v.x, stopLineN5_Westbound + 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (v.x - stopLineN5_Westbound) * 0.04);
                            }
                        }
                    } else if (v.x < node5X && v.x > stopLineN2_Westbound && (v.x - stopLineN2_Westbound) < 140) {
                        if (isNode2_EW_Red) {
                            if (v.x <= stopLineN2_Westbound + 16) {
                                shouldStop = true;
                                v.x = Math.max(v.x, stopLineN2_Westbound + 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (v.x - stopLineN2_Westbound) * 0.04);
                            }
                        }
                    }

                    // Car-following
                    vehicles.forEach((other, oIdx) => {
                        if (idx !== oIdx && other.isEW && other.laneOffset === v.laneOffset) {
                            const gap = v.x - other.x;
                            if (gap > 0 && gap < 28) {
                                shouldStop = true;
                                targetSpeed = Math.min(targetSpeed, other.speed * 0.5);
                                if (gap < 20) {
                                    v.x = other.x + 20;
                                }
                            }
                        }
                    });

                    if (shouldStop) {
                        v.speed = Math.max(0, v.speed - 0.15);
                    } else {
                        v.speed = Math.min(targetSpeed, v.speed + 0.08);
                    }

                    v.x -= v.speed;
                    if (v.x < -40) v.x = w + 30;
                }

                // Render Car Body
                ctx.fillStyle = v.color;
                ctx.beginPath();
                ctx.roundRect(v.x - v.length / 2, laneY - v.width / 2, v.length, v.width, 3);
                ctx.fill();

                // Headlights & Brake/Taillights
                if (isEastbound) {
                    ctx.fillStyle = 'rgba(255, 255, 200, 0.7)';
                    ctx.fillRect(v.x + v.length / 2 - 2, laneY - 3, 2, 2);
                    ctx.fillRect(v.x + v.length / 2 - 2, laneY + 1, 2, 2);
                    // Glowing bright red brake lights when stopped
                    ctx.fillStyle = shouldStop ? '#ff2222' : '#ef4444';
                    ctx.fillRect(v.x - v.length / 2, laneY - 3, 2, 2);
                    ctx.fillRect(v.x - v.length / 2, laneY + 1, 2, 2);
                } else {
                    ctx.fillStyle = 'rgba(255, 255, 200, 0.7)';
                    ctx.fillRect(v.x - v.length / 2, laneY - 3, 2, 2);
                    ctx.fillRect(v.x - v.length / 2, laneY + 1, 2, 2);
                    ctx.fillStyle = shouldStop ? '#ff2222' : '#ef4444';
                    ctx.fillRect(v.x + v.length / 2 - 2, laneY - 3, 2, 2);
                    ctx.fillRect(v.x + v.length / 2 - 2, laneY + 1, 2, 2);
                }

            } else {
                // North-South Avenue Vehicles
                const isNode2Avenue = (v.nodeId === 'Node2');
                const avenueX = isNode2Avenue ? (node2X + v.laneOffset) : (node5X + v.laneOffset);
                const isNSRed = isNode2Avenue ? isNode2_NS_Red : isNode5_NS_Red;
                const isSouthbound = (v.laneOffset > 0);

                if (isSouthbound) {
                    // Moving Down (+y)
                    if (v.y < stopLine_Southbound && (stopLine_Southbound - v.y) < 140) {
                        if (isNSRed) {
                            // Red light on NS approach!
                            if (v.y >= stopLine_Southbound - 16) {
                                shouldStop = true;
                                v.y = Math.min(v.y, stopLine_Southbound - 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (stopLine_Southbound - v.y) * 0.04);
                            }
                        }
                    }

                    // Car-following
                    vehicles.forEach((other, oIdx) => {
                        if (idx !== oIdx && !other.isEW && other.nodeId === v.nodeId && other.laneOffset === v.laneOffset) {
                            const gap = other.y - v.y;
                            if (gap > 0 && gap < 28) {
                                shouldStop = true;
                                targetSpeed = Math.min(targetSpeed, other.speed * 0.5);
                                if (gap < 20) {
                                    v.y = other.y - 20;
                                }
                            }
                        }
                    });

                    if (shouldStop) {
                        v.speed = Math.max(0, v.speed - 0.15);
                    } else {
                        v.speed = Math.min(targetSpeed, v.speed + 0.08);
                    }

                    v.y += v.speed;
                    if (v.y > h + 40) v.y = -30;

                } else {
                    // Moving Up (-y)
                    if (v.y > stopLine_Northbound && (v.y - stopLine_Northbound) < 140) {
                        if (isNSRed) {
                            // Red light on NS approach!
                            if (v.y <= stopLine_Northbound + 16) {
                                shouldStop = true;
                                v.y = Math.max(v.y, stopLine_Northbound + 4);
                            } else {
                                targetSpeed = Math.min(targetSpeed, (v.y - stopLine_Northbound) * 0.04);
                            }
                        }
                    }

                    // Car-following
                    vehicles.forEach((other, oIdx) => {
                        if (idx !== oIdx && !other.isEW && other.nodeId === v.nodeId && other.laneOffset === v.laneOffset) {
                            const gap = v.y - other.y;
                            if (gap > 0 && gap < 28) {
                                shouldStop = true;
                                targetSpeed = Math.min(targetSpeed, other.speed * 0.5);
                                if (gap < 20) {
                                    v.y = other.y + 20;
                                }
                            }
                        }
                    });

                    if (shouldStop) {
                        v.speed = Math.max(0, v.speed - 0.15);
                    } else {
                        v.speed = Math.min(targetSpeed, v.speed + 0.08);
                    }

                    v.y -= v.speed;
                    if (v.y < -40) v.y = h + 30;
                }

                // Render NS Vehicle
                ctx.fillStyle = v.color;
                ctx.beginPath();
                ctx.roundRect(avenueX - v.width / 2, v.y - v.length / 2, v.width, v.length, 3);
                ctx.fill();

                // Brake lights when stopping
                if (isSouthbound) {
                    ctx.fillStyle = shouldStop ? '#ff2222' : '#ef4444';
                    ctx.fillRect(avenueX - 3, v.y - v.length / 2, 2, 2);
                    ctx.fillRect(avenueX + 1, v.y - v.length / 2, 2, 2);
                } else {
                    ctx.fillStyle = shouldStop ? '#ff2222' : '#ef4444';
                    ctx.fillRect(avenueX - 3, v.y + v.length / 2 - 2, 2, 2);
                    ctx.fillRect(avenueX + 1, v.y + v.length / 2 - 2, 2, 2);
                }
            }
        });

        // 4. Render Active Emergency Vehicle (Priority Green Corridor)
        if (hasEmergency) {
            const em = currentTelemetry.active_emergencies[0];
            const progress = (em.progress_pct || 0) / 100;
            const emX = -40 + progress * (w + 80);
            const emY = centerY + 16;

            const timeNow = Date.now() / 120;
            const isRedStrobe = (Math.floor(timeNow) % 2 === 0);

            // Strobe aura
            ctx.beginPath();
            ctx.arc(emX, emY, 26, 0, Math.PI * 2);
            ctx.fillStyle = isRedStrobe ? 'rgba(239, 68, 68, 0.28)' : 'rgba(2, 132, 199, 0.28)';
            ctx.fill();

            // Vehicle Body (White Emergency Chassis)
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.roundRect(emX - 14, emY - 6, 28, 12, 4);
            ctx.fill();

            // Siren Bar
            ctx.fillStyle = isRedStrobe ? '#ef4444' : '#0284c7';
            ctx.fillRect(emX - 4, emY - 4, 8, 3);

            // Identification Label
            ctx.fillStyle = '#f43f5e';
            ctx.font = '700 9px "JetBrains Mono", monospace';
            ctx.fillText(em.vehicle_type || 'EMERGENCY', emX - 22, emY - 10);
        }

        requestAnimationFrame(renderCanvas);
    }
    requestAnimationFrame(renderCanvas);

    // Click on canvas to select intersection node
    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const w = canvas.width;
        if (Math.abs(clickX - (w * 0.32)) < 50) {
            selectedNodeId = 'Node2';
            auditTicker.innerText = 'INSPECTOR: Node 2 (Downtown West) selected for telemetry focus.';
        } else if (Math.abs(clickX - (w * 0.68)) < 50) {
            selectedNodeId = 'Node5';
            auditTicker.innerText = 'INSPECTOR: Node 5 (Downtown East) selected for telemetry focus.';
        }
    });

    // -------------------------------------------------------------
    // Telemetry Polling & Live Data Binding
    // -------------------------------------------------------------
    async function updateTelemetry() {
        try {
            const resp = await fetch('/api/status');
            if (!resp.ok) return;
            const data = await resp.json();
            const tel = data.telemetry;
            currentTelemetry = tel;

            // Status strip
            labelSimStep.innerText = tel.is_running ? `SIM: ACTIVE (STEP ${tel.step})` : 'SIM: PAUSED';
            badgeSimState.className = tel.is_running ? 'status-chip active-green' : 'status-chip';

            labelDbEngine.innerText = `DB: ${data.database_engine.toUpperCase()}`;
            labelAiEngine.innerText = `AI: ${data.anthropic_key_set ? 'CLAUDE 3.5' : 'SEMANTIC SQL'}`;

            if (tel.emergency_count > 0) {
                badgeEmergency.style.display = 'inline-flex';
                document.getElementById('labelEmergencyActive').innerText = `CORRIDOR LOCK: ACTIVE (${tel.emergency_count})`;
            } else {
                badgeEmergency.style.display = 'none';
            }

            // KPIs
            kpiThroughput.innerText = (tel.total_vehicles * 42).toLocaleString();
            kpiWaitTime.innerText = tel.avg_waiting_time_sec;
            kpiQueue.innerText = tel.total_queue_vehicles;
            kpiAvgSpeed.innerText = tel.avg_speed_kmh;

            // Render Nodes Grid
            renderNodesGrid(tel.intersections);

        } catch (err) {
            console.error('Error fetching telemetry:', err);
        }
    }

    function renderNodesGrid(nodes) {
        if (!nodes) return;
        nodesGrid.innerHTML = nodes.map(node => {
            const isRed = node.current_phase >= 2;
            const isYel = node.current_phase === 1;
            const isGrn = node.current_phase === 0;

            const isLocked = node.emergency_override;

            return `
            <div class="node-card ${isLocked ? 'emergency-locked' : ''}">
                <div class="node-card-top">
                    <div class="node-title-group">
                        <h3>${node.name}</h3>
                        <div class="node-sub">${node.id} • Dynamic Webster</div>
                    </div>
                    <div class="signal-head">
                        <div class="lamp lamp-red ${isRed ? 'active' : ''}"></div>
                        <div class="lamp lamp-amber ${isYel ? 'active' : ''}"></div>
                        <div class="lamp lamp-green ${isGrn ? 'active' : ''}"></div>
                    </div>
                </div>

                <div class="node-metrics-table">
                    <div class="node-stat-item">
                        <span class="node-stat-label">Queue</span>
                        <span class="node-stat-val">${node.queue_length} veh</span>
                    </div>
                    <div class="node-stat-item">
                        <span class="node-stat-label">Delay</span>
                        <span class="node-stat-val">${node.waiting_time_sec}s</span>
                    </div>
                    <div class="node-stat-item">
                        <span class="node-stat-label">Speed</span>
                        <span class="node-stat-val">${node.avg_speed_kmh} km/h</span>
                    </div>
                    <div class="node-stat-item">
                        <span class="node-stat-label">Split</span>
                        <span class="node-stat-val" style="color:${isGrn ? 'var(--signal-green)' : 'var(--text-secondary)'}">
                            ${node.phase_name}
                        </span>
                    </div>
                </div>

                <div class="node-badge-row">
                    <span class="status-tag ${node.congestion_level.toLowerCase()}">${node.congestion_level}</span>
                    <span style="font-size:0.68rem; color:${isLocked ? 'var(--signal-green)' : 'var(--text-muted)'}; font-weight:600;">
                        ${isLocked ? '⚡ GREEN LOCK' : 'ADAPTIVE'}
                    </span>
                </div>
            </div>
            `;
        }).join('');
    }

    setInterval(updateTelemetry, 1200);
    updateTelemetry();

    // -------------------------------------------------------------
    // AI Copilot & Text-to-SQL Terminal
    // -------------------------------------------------------------
    async function executeQuery(promptText) {
        if (!promptText || !promptText.trim()) return;

        aiNarrativeText.innerHTML = `
            <div style="color:var(--accent-cyan); display:flex; align-items:center; gap:0.5rem;">
                <span class="pulse-indicator"></span> Transpiling natural language to AST-validated SQL...
            </div>
        `;

        try {
            const resp = await fetch('/api/ai/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: promptText })
            });
            const data = await resp.json();
            currentQueryResult = data;

            perfLatency.innerText = `${data.execution_time_ms || 0}ms`;

            if (!data.success && data.safety_passed === false) {
                // Safety Shield Intercepted Destructive Query!
                safetyStatusPill.className = 'safety-pill blocked';
                safetyStatusPill.innerText = '🛡️ BLOCKED BY SAFETY SHIELD';

                aiNarrativeText.innerHTML = `
                    <div style="color:#fca5a5; font-weight:600; margin-bottom:0.35rem;">Security Violation Intercepted:</div>
                    <div>${data.insight || data.message}</div>
                `;

                sqlCodeBlock.innerText = `-- PROHIBITED DDL/DML INTERCEPTED\n${data.raw_sql || 'N/A'}`;
                countTableRows.innerText = '0';
                tableContainer.innerHTML = '<div style="padding:1rem; color:var(--text-muted); text-align:center;">Query was blocked before execution. No database state changed.</div>';

                auditTicker.innerText = `SECURITY: Blocked suspicious SQL statement "${data.raw_sql.slice(0, 40)}..."`;
                return;
            }

            // Successful Safe Query Execution
            safetyStatusPill.className = 'safety-pill verified';
            safetyStatusPill.innerText = `🛡️ READ-ONLY VERIFIED (${data.database_engine.toUpperCase()})`;

            aiNarrativeText.innerHTML = `<strong>Insight:</strong> ${data.insight}`;
            sqlCodeBlock.innerText = data.generated_sql;

            // Render Table
            if (data.rows && data.rows.length > 0) {
                countTableRows.innerText = data.rows.length;
                const cols = data.columns || Object.keys(data.rows[0]);
                const theadHtml = cols.map(c => `<th>${c}</th>`).join('');
                const tbodyHtml = data.rows.map(r => {
                    return `<tr>${cols.map(c => `<td>${r[c] !== null && r[c] !== undefined ? r[c] : ''}</td>`).join('')}</tr>`;
                }).join('');

                tableContainer.innerHTML = `
                    <table class="enterprise-table">
                        <thead><tr>${theadHtml}</tr></thead>
                        <tbody>${tbodyHtml}</tbody>
                    </table>
                `;
            } else {
                countTableRows.innerText = '0';
                tableContainer.innerHTML = '<div style="padding:1rem; color:var(--text-muted); text-align:center;">No rows returned.</div>';
            }

            auditTicker.innerText = `AI COPILOT: Generated safe SQL query in ${data.execution_time_ms}ms. Retrieved ${data.row_count || 0} rows.`;

        } catch (err) {
            aiNarrativeText.innerText = `Error: ${err.message}`;
        }
    }

    btnSendQuery.addEventListener('click', () => {
        executeQuery(terminalInput.value);
    });

    terminalInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            executeQuery(terminalInput.value);
        }
    });

    // Preset Prompt Chips
    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', () => {
            const q = chip.getAttribute('data-query');
            terminalInput.value = q;
            executeQuery(q);
        });
    });

    // -------------------------------------------------------------
    // Tab Switching
    // -------------------------------------------------------------
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.style.display = 'none');

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.style.display = 'block';
        });
    });

    // -------------------------------------------------------------
    // Export CSV & Copy SQL Utilities
    // -------------------------------------------------------------
    if (btnCopySql) {
        btnCopySql.addEventListener('click', () => {
            const sql = sqlCodeBlock.innerText;
            navigator.clipboard.writeText(sql).then(() => {
                btnCopySql.innerText = 'Copied!';
                setTimeout(() => { btnCopySql.innerText = 'Copy SQL'; }, 1500);
            });
        });
    }

    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', () => {
            if (!currentQueryResult || !currentQueryResult.rows || currentQueryResult.rows.length === 0) {
                alert('No query data available to export.');
                return;
            }
            const rows = currentQueryResult.rows;
            const cols = currentQueryResult.columns || Object.keys(rows[0]);
            let csv = cols.join(',') + '\n';
            rows.forEach(r => {
                csv += cols.map(c => JSON.stringify(r[c] || '')).join(',') + '\n';
            });

            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `traffic_analytics_${Date.now()}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    // -------------------------------------------------------------
    // Operations & Simulation Controls
    // -------------------------------------------------------------
    btnAmbulance.addEventListener('click', async () => {
        await fetch('/api/emergency/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_type: 'AMBULANCE', route: 'Downtown Corridor (Node2 -> Node5)' })
        });
        auditTicker.innerText = 'PRIORITY OVERRIDE: Ambulance dispatched. Corridor green-wave activated.';
        updateTelemetry();
    });

    btnFireRescue.addEventListener('click', async () => {
        await fetch('/api/emergency/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_type: 'FIRE_ENGINE', route: 'Downtown Corridor (Node2 -> Node5)' })
        });
        auditTicker.innerText = 'PRIORITY OVERRIDE: Fire Rescue dispatched. Corridor green-wave activated.';
        updateTelemetry();
    });

    btnToggleSim.addEventListener('click', async () => {
        const resp = await fetch('/api/simulation/toggle', { method: 'POST' });
        const res = await resp.json();
        labelSimBtn.innerText = res.is_running ? 'Pause' : 'Resume';
        updateTelemetry();
    });

    // Execute baseline query on launch
    executeQuery(terminalInput.value);
});
