// app.js - AMEVA Edge Matrix Core controller

let activeTab = 'dashboard';
let currentActiveModel = null;
let currentActiveEngine = 'OLM';
let telemetryWs = null;
let logsWs = null;

// Local Harness state
let harnessTasks = [];

// Telemetry History
const cpuHistory = [];
const gpuHistory = [];
const historyLimit = 50;

// Initialize
window.addEventListener('DOMContentLoaded', () => {
    initWebSockets();
    startSessionStatusPolling();
    loadReports();
    initCanvas();
});

// ─────────────────────────────────────────────────────────────────────────────
// WebSockets (Telemetry & Logs)
// ─────────────────────────────────────────────────────────────────────────────

function initWebSockets() {
    const host = window.location.host;
    
    // Telemetry WebSocket
    telemetryWs = new WebSocket(`ws://${host}/ws/telemetry`);
    telemetryWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateTelemetry(data);
    };
    telemetryWs.onclose = () => {
        setTimeout(initWebSockets, 3000); // 3초 후 재연결 시도
    };

    // Logs & Chunks WebSocket
    logsWs = new WebSocket(`ws://${host}/ws/logs`);
    logsWs.onmessage = (event) => {
        const packet = JSON.parse(event.data);
        handleIncomingLog(packet);
    };
    logsWs.onclose = () => {
        setTimeout(initWebSockets, 3000);
    };
}

function updateTelemetry(data) {
    // Text update
    document.getElementById('val-cpu').innerText = `${data.cpu.toFixed(1)}%`;
    document.getElementById('val-ram').innerText = `${data.ram.toFixed(1)} / ${data.ram_total.toFixed(1)} GB`;
    document.getElementById('val-gpu').innerText = `${data.gpu_percent.toFixed(1)}%`;
    document.getElementById('val-vram').innerText = `${Math.round(data.vram_used_mb)} / ${Math.round(data.vram_total_mb)} MB`;
    
    // Progress Bar update
    document.getElementById('bar-cpu').style.width = `${data.cpu}%`;
    document.getElementById('bar-ram').style.width = `${(data.ram / data.ram_total) * 100}%`;
    document.getElementById('bar-gpu').style.width = `${data.gpu_percent}%`;
    const vramPct = data.vram_total_mb > 0 ? (data.vram_used_mb / data.vram_total_mb) * 100 : 0;
    document.getElementById('bar-vram').style.width = `${vramPct}%`;

    // Power & Temperature info
    const power = data.power_w ? `${data.power_w.toFixed(1)}W` : 'N/A';
    const temp = data.temp_c ? `${data.temp_c}°C` : 'N/A';
    document.getElementById('val-power-temp').innerText = `전력: ${power}  |  온도: ${temp}`;

    // Graph data accumulation
    cpuHistory.push(data.cpu);
    gpuHistory.push(data.gpu_percent);
    if (cpuHistory.length > historyLimit) cpuHistory.shift();
    if (gpuHistory.length > historyLimit) gpuHistory.shift();

    drawTelemetryGraph();
}

function handleIncomingLog(packet) {
    const type = packet.type;
    const text = packet.text;

    let targetViewportId = 'log-viewport-sys';
    if (type === 'bench') {
        targetViewportId = 'log-viewport-bench';
    } else if (type === 'chunk') {
        targetViewportId = 'log-viewport-stream';
        // 만약 대화창에서 AI가 작성중이라면 대화 버블로 복제해줌
        appendChatChunk(text);
    }

    const viewport = document.getElementById(targetViewportId);
    if (!viewport) return;

    const line = document.createElement('div');
    line.className = 'log-line';
    line.innerText = text;
    viewport.appendChild(line);

    // Auto-scroll
    viewport.scrollTop = viewport.scrollHeight;

    // Limit log lines to 1000
    if (viewport.childNodes.length > 1000) {
        viewport.removeChild(viewport.firstChild);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Telemetry Canvas Chart (Vanilla Graphics)
// ─────────────────────────────────────────────────────────────────────────────

let canvas, ctx;
function initCanvas() {
    canvas = document.getElementById('telemetry-canvas');
    ctx = canvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
}

function resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = 80;
    drawTelemetryGraph();
}

function drawTelemetryGraph() {
    if (!canvas || !ctx) return;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Draw grid
    ctx.strokeStyle = 'rgba(46, 59, 78, 0.3)';
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
        const y = (h / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }

    const step = w / (historyLimit - 1);

    // Draw CPU Line (Light Blue)
    drawDataLine(cpuHistory, step, '#3b82f6', 'rgba(59, 130, 246, 0.08)');

    // Draw GPU Line (Green)
    drawDataLine(gpuHistory, step, '#10b981', 'rgba(16, 185, 129, 0.08)');
}

function drawDataLine(history, step, color, fillGradientColor) {
    if (history.length < 2) return;
    const h = canvas.height;

    ctx.beginPath();
    history.forEach((val, i) => {
        const x = i * step;
        const y = h - (val / 100) * (h - 6) - 3;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Fill under line
    ctx.lineTo((history.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = fillGradientColor;
    ctx.fill();
}

// ─────────────────────────────────────────────────────────────────────────────
// Active Session & Kernel Boot Sequence
// ─────────────────────────────────────────────────────────────────────────────

function startSessionStatusPolling() {
    setInterval(checkSessionStatus, 2000);
}

async function checkSessionStatus() {
    try {
        const resp = await fetch('/api/session/status');
        const data = await resp.json();
        
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        
        statusDot.className = 'status-indicator';
        
        if (data.boot_status === 'ONLINE') {
            statusDot.classList.add('online');
            statusText.innerText = `온라인 - 커널 동작중 [${data.boot_message}]`;
            
            document.getElementById('btn-boot').disabled = true;
            document.getElementById('btn-shutdown').disabled = false;
            
            currentActiveModel = data.last_booted_model;
            document.getElementById('active-model-display').innerText = currentActiveModel || "모델 미선택";
            document.getElementById('active-model-display').style.color = "var(--accent)";
        } else if (data.boot_status === 'BOOTING') {
            statusDot.classList.add('booting');
            statusText.innerText = `가동중 - 커널 격리 공간 준비 중...`;
            
            document.getElementById('btn-boot').disabled = true;
            document.getElementById('btn-shutdown').disabled = true;
        } else if (data.boot_status === 'ERROR') {
            statusDot.classList.add('offline');
            statusText.innerText = `장애발생 - ${data.boot_message}`;
            
            document.getElementById('btn-boot').disabled = false;
            document.getElementById('btn-shutdown').disabled = true;
        } else {
            // OFFLINE
            statusText.innerText = `오프라인 - 커널 동작 정지 상태`;
            document.getElementById('btn-boot').disabled = false;
            document.getElementById('btn-shutdown').disabled = true;
            document.getElementById('active-model-display').innerText = "미선택 (OFFLINE)";
            document.getElementById('active-model-display').style.color = "var(--text-muted)";
        }

        // Benchmark Run Button Disable if already running
        const runBtn = document.getElementById('btn-run');
        if (data.benchmark_running || data.chat_running) {
            runBtn.disabled = true;
            runBtn.innerText = "⏳ RUNNING TASK...";
        } else {
            runBtn.disabled = false;
            runBtn.innerText = "⚡ RUN BENCHMARK";
        }
    } catch (e) {
        console.error("Status check failed", e);
    }
}

async function bootKernel() {
    const engine = document.getElementById('config-engine').value;
    const cpu = parseFloat(document.getElementById('config-cpu').value);
    const ram = parseInt(document.getElementById('config-ram').value);
    const gpu = parseInt(document.getElementById('config-gpu').value);
    
    if (!currentActiveModel) {
        alert("가동할 모델을 먼저 선택해주세요!");
        openModelGallery();
        return;
    }

    try {
        const resp = await fetch('/api/session/boot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                engine: engine,
                cpu_cores: cpu,
                ram_mb: ram,
                gpu_layers: gpu,
                model_name: currentActiveModel
            })
        });
        if (resp.ok) {
            switchLogTab('sys');
            document.getElementById('log-viewport-sys').innerText = ""; // Clear logs
        } else {
            const err = await resp.json();
            alert(`커널 가동 요청 실패: ${err.detail}`);
        }
    } catch (e) {
        alert(`네트워크 통신 실패: ${e}`);
    }
}

async function shutdownKernel() {
    if (!confirm("커널을 정말 셧다운 하시겠습니까? Docker 리소스가 완전히 해제됩니다.")) return;
    
    try {
        const resp = await fetch('/api/session/shutdown', { method: 'POST' });
        if (resp.ok) {
            alert("커널 셧다운 시퀀스가 실행되었습니다.");
        }
    } catch (e) {
        alert("네트워크 오류");
    }
}

function onEngineChange() {
    const engine = document.getElementById('config-engine').value;
    currentActiveEngine = engine;
}

// ─────────────────────────────────────────────────────────────────────────────
// Model Gallery Modal
// ─────────────────────────────────────────────────────────────────────────────

async function openModelGallery() {
    document.getElementById('modal-gallery').classList.add('active');
    await loadGalleryModels();
}

function closeModal(modalId) {
    document.getElementById(`modal-${modalId}`).classList.remove('active');
}

async function loadGalleryModels() {
    const container = document.getElementById('gallery-body');
    container.innerHTML = "<div style='color:var(--text-muted); padding:20px; text-align:center;'>모델 레지스트리 로딩 중...</div>";
    
    try {
        const resp = await fetch('/api/models');
        const data = await resp.json();
        
        container.innerHTML = "";
        
        // Group models by category
        const categories = {};
        data.models.forEach(m => {
            if (!categories[m.category]) categories[m.category] = [];
            categories[m.category].push(m);
        });

        // Loop categories
        for (const [catName, catModels] of Object.entries(categories)) {
            const meta = data.categories[catName];
            
            const catDiv = document.createElement('div');
            catDiv.className = 'model-category';
            
            const header = document.createElement('div');
            header.className = 'model-category-header';
            header.style.color = meta.color;
            header.style.borderBottomColor = meta.color;
            header.innerText = `${meta.icon} ${catName} — ${meta.desc}`;
            catDiv.appendChild(header);

            const cardsDiv = document.createElement('div');
            cardsDiv.className = 'model-cards';

            catModels.forEach(model => {
                const card = document.createElement('div');
                card.className = 'model-card';
                if (model.id === currentActiveModel || model.ollama_tag === currentActiveModel) {
                    card.style.borderColor = 'var(--primary)';
                    card.style.backgroundColor = 'rgba(59, 130, 246, 0.05)';
                }

                // Left Block
                const left = document.createElement('div');
                left.className = 'model-card-info';
                
                const title = document.createElement('div');
                title.className = 'model-card-title';
                title.innerHTML = `<span>${model.display}</span><span class="model-card-tag">${model.tag}</span>`;
                left.appendChild(title);

                const desc = document.createElement('div');
                desc.className = 'model-card-desc';
                desc.innerText = model.desc;
                left.appendChild(desc);

                const metaDiv = document.createElement('div');
                metaDiv.className = 'model-card-meta';
                metaDiv.innerText = `최소 RAM: ${model.min_ram_gb}GB  |  크기: ~${model.size_gb.toFixed(1)}GB  |  Ollama: ${model.ollama_tag}`;
                left.appendChild(metaDiv);

                if (model.download.status === 'downloading') {
                    const progContainer = document.createElement('div');
                    progContainer.className = 'download-progress-container';
                    progContainer.innerHTML = `
                        <div style="font-size:10px; color:var(--warn); margin-bottom:2px;">설치 중: ${model.download.progress}%</div>
                        <div class="progress-track"><div class="progress-fill" style="width:${model.download.progress}%; background-color:var(--warn);"></div></div>
                    `;
                    left.appendChild(progContainer);
                }

                card.appendChild(left);

                // Right Block (Buttons)
                const right = document.createElement('div');
                right.className = 'model-card-actions';

                // GGUF Download / Select
                const ggufBtn = document.createElement('button');
                ggufBtn.className = 'btn';
                if (model.gguf_installed) {
                    ggufBtn.classList.add('btn-primary');
                    ggufBtn.innerText = "▶ 사용 (GGUF)";
                    ggufBtn.onclick = () => selectModel(model.id, currentActiveEngine === 'BIT' ? 'BIT' : 'ENG');
                } else if (model.download.status === 'downloading' && currentActiveEngine !== 'OLM') {
                    ggufBtn.innerText = "⏳ 취소";
                    ggufBtn.classList.add('btn-danger');
                    ggufBtn.onclick = () => cancelDownload(model.id);
                } else {
                    ggufBtn.innerText = "📦 GGUF 다운로드";
                    ggufBtn.onclick = () => downloadModel(model.id, false, currentActiveEngine === 'BIT' ? 'BIT' : 'ENG');
                }
                right.appendChild(ggufBtn);

                // Ollama Pull / Select
                const ollamaBtn = document.createElement('button');
                ollamaBtn.className = 'btn';
                if (model.ollama_installed) {
                    ollamaBtn.classList.add('btn-accent');
                    ollamaBtn.innerText = "▶ 사용 (Ollama)";
                    ollamaBtn.onclick = () => selectModel(model.ollama_tag, 'OLM');
                } else if (model.download.status === 'downloading' && currentActiveEngine === 'OLM') {
                    ollamaBtn.innerText = "⏳ 취소";
                    ollamaBtn.classList.add('btn-danger');
                    ollamaBtn.onclick = () => cancelDownload(model.id);
                } else {
                    ollamaBtn.innerText = "🦙 Ollama 풀링";
                    ollamaBtn.onclick = () => downloadModel(model.id, true, 'OLM');
                }
                right.appendChild(ollamaBtn);

                card.appendChild(right);
                cardsDiv.appendChild(card);
            });

            catDiv.appendChild(cardsDiv);
            container.appendChild(catDiv);
        }
    } catch (e) {
        container.innerHTML = `<div style='color:var(--danger); padding:20px; text-align:center;'>오류 발생: ${e}</div>`;
    }
}

async function selectModel(modelName, engineType) {
    currentActiveModel = modelName;
    document.getElementById('config-engine').value = engineType;
    currentActiveEngine = engineType;
    document.getElementById('active-model-display').innerText = modelName;
    document.getElementById('active-model-display').style.color = "var(--accent)";
    closeModal('gallery');
    
    // Status polling will sync everything
    alert(`모델이 선택되었습니다: ${modelName} (${engineType})`);
}

async function downloadModel(modelId, isOllama, engineType) {
    try {
        const resp = await fetch('/api/models/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_id: modelId,
                is_ollama: isOllama,
                engine_type: engineType
            })
        });
        if (resp.ok) {
            loadGalleryModels(); // Refresh view
            // Poll for gallery updates in background while modal is open
            startGalleryPolling();
        }
    } catch(e) {
        alert("다운로드 요청 실패");
    }
}

async function cancelDownload(modelId) {
    try {
        const resp = await fetch(`/api/models/cancel?model_id=${modelId}`, { method: 'POST' });
        if (resp.ok) {
            loadGalleryModels();
        }
    } catch(e) {
        alert("취소 요청 실패");
    }
}

let galleryInterval = null;
function startGalleryPolling() {
    if (galleryInterval) clearInterval(galleryInterval);
    galleryInterval = setInterval(() => {
        const modal = document.getElementById('modal-gallery');
        if (modal.classList.contains('active')) {
            loadGalleryModels();
        } else {
            clearInterval(galleryInterval);
            galleryInterval = null;
        }
    }, 2000);
}

// ─────────────────────────────────────────────────────────────────────────────
// Harness Manager Modal
// ─────────────────────────────────────────────────────────────────────────────

async function openHarnessManager() {
    document.getElementById('modal-harness').classList.add('active');
    await loadHarnessData();
}

async function loadHarnessData() {
    const tableBody = document.getElementById('harness-table-body');
    tableBody.innerHTML = "<tr><td colspan='5' style='text-align:center;'>로드 중...</td></tr>";
    
    try {
        const resp = await fetch('/api/harness');
        harnessTasks = await resp.json();
        renderHarnessTable();
    } catch (e) {
        tableBody.innerHTML = "<tr><td colspan='5' style='text-align:center;color:var(--danger);'>로딩 에러</td></tr>";
    }
}

function renderHarnessTable() {
    const tableBody = document.getElementById('harness-table-body');
    tableBody.innerHTML = "";
    
    if (harnessTasks.length === 0) {
        tableBody.innerHTML = "<tr><td colspan='5' style='text-align:center;color:var(--text-muted);'>등록된 태스크가 없습니다.</td></tr>";
        return;
    }

    harnessTasks.forEach((task, index) => {
        const tr = document.createElement('tr');
        
        const tdId = document.createElement('td');
        tdId.innerText = task.task;
        tdId.style.fontWeight = '700';
        tdId.style.color = '#fff';
        tr.appendChild(tdId);

        const tdPrompt = document.createElement('td');
        tdPrompt.innerText = task.prompt;
        tdPrompt.style.whiteSpace = 'nowrap';
        tdPrompt.style.overflow = 'hidden';
        tdPrompt.style.textOverflow = 'ellipsis';
        tdPrompt.style.maxWidth = '300px';
        tr.appendChild(tdPrompt);

        const tdRegex = document.createElement('td');
        tdRegex.innerText = task.expected_regex || "-";
        tr.appendChild(tdRegex);

        const tdEval = document.createElement('td');
        tdEval.innerText = task.eval_type;
        tdEval.style.color = task.eval_type === 'llm_judge' ? '#60a5fa' : '#34d399';
        tr.appendChild(tdEval);

        const tdActions = document.createElement('td');
        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-danger';
        delBtn.style.padding = '3px 8px';
        delBtn.style.fontSize = '11px';
        delBtn.innerText = "🗑️";
        delBtn.onclick = () => deleteHarnessTask(index);
        tdActions.appendChild(delBtn);
        tr.appendChild(tdActions);

        tableBody.appendChild(tr);
    });
}

function onNewTaskEvalChange() {
    const evalType = document.getElementById('new-task-eval').value;
    const regexGroup = document.getElementById('new-task-regex-group');
    if (evalType === 'regex') {
        regexGroup.style.display = 'block';
    } else {
        regexGroup.style.display = 'none';
    }
}

function addHarnessTask() {
    const idInput = document.getElementById('new-task-id');
    const promptInput = document.getElementById('new-task-prompt');
    const evalInput = document.getElementById('new-task-eval');
    const regexInput = document.getElementById('new-task-regex');
    
    if (!idInput.value.trim() || !promptInput.value.trim()) {
        alert("TASK ID와 PROMPT를 채워주세요.");
        return;
    }

    const task = {
        task: idInput.value.trim(),
        prompt: promptInput.value.trim(),
        eval_type: evalInput.value,
        expected_regex: evalInput.value === 'regex' ? regexInput.value.trim() : ""
    };

    harnessTasks.push(task);
    renderHarnessTable();

    // Reset inputs
    idInput.value = "";
    promptInput.value = "";
    regexInput.value = "";
}

function deleteHarnessTask(index) {
    harnessTasks.splice(index, 1);
    renderHarnessTable();
}

async function commitHarness() {
    try {
        const resp = await fetch('/api/harness', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(harnessTasks)
        });
        if (resp.ok) {
            alert("harness_v4.csv 에 성공적으로 저장 및 커밋되었습니다.");
            closeModal('harness');
        } else {
            alert("저장 실패");
        }
    } catch(e) {
        alert("네트워크 통신 장애");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Benchmark Run Sequence
// ─────────────────────────────────────────────────────────────────────────────

async function runBenchmark() {
    const runMode = document.getElementById('run-mode').value;
    const engine = document.getElementById('config-engine').value;
    const cpu = parseFloat(document.getElementById('config-cpu').value);
    const ram = parseInt(document.getElementById('config-ram').value);
    const gpu = parseInt(document.getElementById('config-gpu').value);
    
    const threads = parseInt(document.getElementById('stress-threads').value);
    const nctx = parseInt(document.getElementById('stress-nctx').value);
    const temp = parseFloat(document.getElementById('stress-temp').value);
    const penalty = parseFloat(document.getElementById('stress-penalty').value);
    const sysPrompt = document.getElementById('stress-sysprompt').value;
    const judgeModel = document.getElementById('stress-judgemodel').value;

    if (!currentActiveModel) {
        alert("실행할 액티브 모델을 먼저 선택해주세요!");
        openModelGallery();
        return;
    }

    // Clear logs
    document.getElementById('log-viewport-sys').innerText = "";
    document.getElementById('log-viewport-bench').innerText = "";
    document.getElementById('log-viewport-stream').innerText = "";
    
    switchLogTab('bench');

    try {
        const resp = await fetch('/api/benchmark/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                boot_config: {
                    engine: engine,
                    cpu_cores: cpu,
                    ram_mb: ram,
                    gpu_layers: gpu,
                    model_name: currentActiveModel
                },
                stress_config: {
                    threads: threads,
                    n_ctx: nctx,
                    iterations: 1,
                    temperature: temp,
                    top_k: 40,
                    top_p: 0.95,
                    repeat_penalty: penalty,
                    system_prompt: sysPrompt,
                    judge_model: judgeModel
                },
                run_mode: runMode
            })
        });

        if (resp.ok) {
            alert("벤치마크 작업 시퀀스가 정상 접수되었습니다. 로그 탭을 확인하세요.");
        } else {
            const err = await resp.json();
            alert(`벤치마크 실행 실패: ${err.detail}`);
        }
    } catch(e) {
        alert("네트워크 장애");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Interactive Chat
// ─────────────────────────────────────────────────────────────────────────────

let activeAiBubble = null;

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const prompt = input.value.trim();
    if (!prompt) return;

    if (!currentActiveModel) {
        alert("채팅 모델을 선택해주세요!");
        openModelGallery();
        return;
    }

    input.value = "";

    // Append User Message
    appendChatBubble(prompt, 'user');

    // Create and Append AI Pending Message
    activeAiBubble = appendChatBubble("⏳ AI 추론 중…", 'ai');
    document.getElementById('log-viewport-stream').innerText = ""; // Clear stream view
    switchLogTab('stream');

    const engine = document.getElementById('config-engine').value;
    const cpu = parseFloat(document.getElementById('config-cpu').value);
    const ram = parseInt(document.getElementById('config-ram').value);
    const gpu = parseInt(document.getElementById('config-gpu').value);
    
    const threads = parseInt(document.getElementById('stress-threads').value);
    const nctx = parseInt(document.getElementById('stress-nctx').value);
    const temp = parseFloat(document.getElementById('stress-temp').value);
    const penalty = parseFloat(document.getElementById('stress-penalty').value);
    const sysPrompt = document.getElementById('stress-sysprompt').value;
    const judgeModel = document.getElementById('stress-judgemodel').value;

    try {
        const resp = await fetch('/api/benchmark/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                boot_config: {
                    engine: engine,
                    cpu_cores: cpu,
                    ram_mb: ram,
                    gpu_layers: gpu,
                    model_name: currentActiveModel
                },
                stress_config: {
                    threads: threads,
                    n_ctx: nctx,
                    iterations: 1,
                    temperature: temp,
                    top_k: 40,
                    top_p: 0.95,
                    repeat_penalty: penalty,
                    system_prompt: sysPrompt,
                    judge_model: judgeModel
                }
            })
        });

        if (!resp.ok) {
            const err = await resp.json();
            activeAiBubble.innerText = `❌ 오류: ${err.detail}`;
            activeAiBubble = null;
        }
    } catch(e) {
        activeAiBubble.innerText = `❌ 통신 장매 발생`;
        activeAiBubble = null;
    }
}

function appendChatBubble(text, sender) {
    const container = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;
    bubble.innerText = text;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
    return bubble;
}

function appendChatChunk(chunk) {
    if (activeAiBubble) {
        if (activeAiBubble.innerText === "⏳ AI 추론 중…") {
            activeAiBubble.innerText = "";
        }
        // Judge Rationale가 진행될 때 구분선 처리
        if (chunk.includes("Local Judge Thought")) {
            activeAiBubble.innerHTML += `<div style="margin-top:12px; padding-top:10px; border-top:1px dashed var(--border-color); color:var(--warn); font-size:11px; font-family:monospace;">${chunk}</div>`;
        } else {
            activeAiBubble.innerText += chunk;
        }
        const container = document.getElementById('chat-messages');
        container.scrollTop = container.scrollHeight;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reports View
// ─────────────────────────────────────────────────────────────────────────────

async function loadReports() {
    const tbody = document.getElementById('reports-table-body');
    
    try {
        const resp = await fetch('/api/reports');
        const data = await resp.json();
        
        tbody.innerHTML = "";
        if (data.length === 0) {
            tbody.innerHTML = "<tr><td colspan='9' style='text-align: center; color: var(--text-muted);'>데이터가 없습니다.</td></tr>";
            return;
        }

        data.forEach(r => {
            const tr = document.createElement('tr');
            
            const timestamp = r.Timestamp || "-";
            const model = r.Model_Hash || "-";
            const category = r.Benchmark_Category || "-";
            const ttft = r["TTFT (ms)"] ? `${r["TTFT (ms)"]} ms` : "-";
            const tps = r["Generation (t/s)"] ? `${r["Generation (t/s)"]} t/s` : "-";
            const watts = r["Avg_GPU_W"] ? `${r["Avg_GPU_W"]} W` : "-";
            const eff = r["Tokens_per_Joule"] ? r["Tokens_per_Joule"] : "-";
            const score = r["Judge_Score"] || "-";
            
            let reason = r["Judge_Reason"] || "-";
            if (reason.length > 50) reason = reason.substring(0, 50) + "...";

            tr.innerHTML = `
                <td>${timestamp}</td>
                <td style="font-weight:700;">${model}</td>
                <td>${category}</td>
                <td>${ttft}</td>
                <td>${tps}</td>
                <td>${watts}</td>
                <td>${eff}</td>
                <td style="font-weight:700; color:var(--accent);">${score}</td>
                <td title="${r["Judge_Reason"] || ""}">${reason}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = "<tr><td colspan='9' style='text-align: center; color: var(--danger);'>로드 실패</td></tr>";
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// UI Helpers & Navigation
// ─────────────────────────────────────────────────────────────────────────────

function switchTab(tabId) {
    activeTab = tabId;
    
    // Header Buttons Active State
    const btns = document.querySelectorAll('.nav-tabs .tab-btn');
    btns.forEach(btn => {
        if (btn.getAttribute('onclick').includes(tabId)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Content Display
    const panes = document.querySelectorAll('.tab-pane');
    panes.forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    if (tabId === 'reports') {
        loadReports();
    }
}

function switchLogTab(logId) {
    const tabs = document.querySelectorAll('.log-tabs .log-tab');
    tabs.forEach(tab => {
        if (tab.id === `log-tab-${logId}`) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    const viewports = document.querySelectorAll('.log-panel .log-viewport');
    viewports.forEach(viewport => {
        if (viewport.id === `log-viewport-${logId}`) {
            viewport.style.display = 'block';
        } else {
            viewport.style.display = 'none';
        }
    });
}
