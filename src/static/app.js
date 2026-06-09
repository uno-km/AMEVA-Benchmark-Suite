// app.js - AMEVA Edge Matrix Core controller (SQLite + Word/Excel Reporting)

let activeTab = 'dashboard';
let currentActiveModel = null;
let currentActiveEngine = 'OLM';
let telemetryWs = null;
let logsWs = null;
let currentDetailedResults = [];

// Local Harness state
let harnessTasks = [];

// Telemetry History
const cpuHistory = [];
const gpuHistory = [];
const historyLimit = 50;

// Initialize
window.addEventListener('DOMContentLoaded', async () => {
    initWebSockets();
    startSessionStatusPolling();
    loadReports();
    initCanvas();
    await loadConfigFromBackend();
    await loadOllamaJudgeModels();
});

// ─────────────────────────────────────────────────────────────────────────────
// WebSockets (Telemetry & Logs)
// ─────────────────────────────────────────────────────────────────────────────

function initWebSockets() {
    initTelemetryWs();
    initLogsWs();
}

function initTelemetryWs() {
    const host = window.location.host;
    if (telemetryWs && telemetryWs.readyState === WebSocket.OPEN) return;
    telemetryWs = new WebSocket(`ws://${host}/ws/telemetry`);
    telemetryWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateTelemetry(data);
        } catch(e) {}
    };
    telemetryWs.onclose = () => {
        setTimeout(initTelemetryWs, 3000);
    };
    telemetryWs.onerror = () => {
        telemetryWs.close();
    };
}

function initLogsWs() {
    const host = window.location.host;
    if (logsWs && logsWs.readyState === WebSocket.OPEN) return;
    logsWs = new WebSocket(`ws://${host}/ws/logs`);
    logsWs.onmessage = (event) => {
        try {
            const packet = JSON.parse(event.data);
            handleIncomingLog(packet);
        } catch(e) {}
    };
    logsWs.onclose = () => {
        setTimeout(initLogsWs, 3000);
    };
    logsWs.onerror = () => {
        logsWs.close();
    };
}

function updateTelemetry(data) {
    document.getElementById('val-cpu').innerText = `${data.cpu.toFixed(1)}%`;
    document.getElementById('val-ram').innerText = `${data.ram.toFixed(1)} / ${data.ram_total.toFixed(1)} GB`;
    document.getElementById('val-gpu').innerText = `${data.gpu_percent.toFixed(1)}%`;
    document.getElementById('val-vram').innerText = `${Math.round(data.vram_used_mb)} / ${Math.round(data.vram_total_mb)} MB`;
    
    document.getElementById('bar-cpu').style.width = `${data.cpu}%`;
    document.getElementById('bar-ram').style.width = `${(data.ram / data.ram_total) * 100}%`;
    document.getElementById('bar-gpu').style.width = `${data.gpu_percent}%`;
    const vramPct = data.vram_total_mb > 0 ? (data.vram_used_mb / data.vram_total_mb) * 100 : 0;
    document.getElementById('bar-vram').style.width = `${vramPct}%`;

    const power = data.power_w ? `${data.power_w.toFixed(1)}W` : 'N/A';
    const temp = data.temp_c ? `${data.temp_c}°C` : 'N/A';
    document.getElementById('val-power-temp').innerText = `전력: ${power}  |  온도: ${temp}`;

    cpuHistory.push(data.cpu);
    gpuHistory.push(data.gpu_percent);
    if (cpuHistory.length > historyLimit) cpuHistory.shift();
    if (gpuHistory.length > historyLimit) gpuHistory.shift();

    drawTelemetryGraph();
}

function handleIncomingLog(packet) {
    const type = packet.type;
    const text = packet.text;

    if (type === 'chunk') {
        // 실시간 스트리밍: 스트림 뷰포트에 span으로 가로 연결
        const streamViewport = document.getElementById('log-viewport-stream');
        if (streamViewport) {
            const tokenSpan = document.createElement('span');
            tokenSpan.textContent = text;
            streamViewport.appendChild(tokenSpan);
            streamViewport.scrollTop = streamViewport.scrollHeight;
        }
        // 채팅 버블에도 반영
        appendChatChunk(text);
        return;
    }

    let targetViewportId = 'log-viewport-sys';
    if (type === 'bench') {
        targetViewportId = 'log-viewport-bench';
    }

    const viewport = document.getElementById(targetViewportId);
    if (!viewport) return;

    // 텍스트를 줄 단위로 분할하여 각각 div.log-line으로 추가
    const lines = text.split('\n');
    lines.forEach((lineText, idx) => {
        if (idx === 0 && viewport.lastChild && viewport.lastChild.classList && viewport.lastChild.classList.contains('log-line')) {
            // 마지막 줄에 이어 붙이지 않고 새 줄 생성
        }
        const line = document.createElement('div');
        line.className = 'log-line';
        if (type === 'bench') {
            if (lineText.includes("====== ###")) {
                line.style.color = '#ff9800'; // Orange
                line.style.fontWeight = 'bold';
            } else {
                line.style.color = 'var(--accent)';
            }
        }
        line.textContent = lineText;
        viewport.appendChild(line);
    });

    viewport.scrollTop = viewport.scrollHeight;

    // 최대 3000줄 유지 (메모리 관리)
    while (viewport.childNodes.length > 3000) {
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
    drawDataLine(cpuHistory, step, '#3b82f6', 'rgba(59, 130, 246, 0.08)');
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

    ctx.lineTo((history.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = fillGradientColor;
    ctx.fill();
}

// ─────────────────────────────────────────────────────────────────────────────
// Config & Settings (JSON Config)
// ─────────────────────────────────────────────────────────────────────────────

async function loadConfigFromBackend() {
    try {
        const resp = await fetch('/api/config');
        const data = await resp.json();
        
        document.getElementById('stress-judgemodel').value = data.default_judge_model || "exaone3.5:7.8b";
        document.getElementById('config-engine').value = data.last_used_engine || "OLM";
        document.getElementById('config-cpu').value = data.last_used_cores || 2.0;
        document.getElementById('config-ram').value = data.last_used_ram || 4096;
        document.getElementById('config-gpu').value = data.last_used_gpu_layers || 0;
        
        currentActiveEngine = data.last_used_engine || "OLM";
    } catch(e) {
        console.error("Config load failed", e);
    }
}

async function loadOllamaJudgeModels() {
    try {
        const select = document.getElementById('select-judge-model');
        const currentSelectedVal = document.getElementById('stress-judgemodel').value;
        
        // 로딩 표시
        select.innerHTML = '<option value="">-- 모델 로딩 중... --</option>';
        
        const resp = await fetch('/api/models/installed-ollama');
        const data = await resp.json();
        
        select.innerHTML = '<option value="">-- 설치된 Ollama 모델 선택 --</option>';
        
        if (data.models && data.models.length > 0) {
            data.models.forEach(modelName => {
                const opt = document.createElement('option');
                opt.value = modelName;
                opt.innerText = modelName;
                if (modelName === currentSelectedVal) {
                    opt.selected = true;
                }
                select.appendChild(opt);
            });
        } else {
            const opt = document.createElement('option');
            opt.value = "";
            opt.innerText = "-- 설치된 모델 없음 (Ollama 기동 확인) --";
            select.appendChild(opt);
        }
    } catch(e) {
        console.error("Failed to load Ollama judge models", e);
        const select = document.getElementById('select-judge-model');
        select.innerHTML = '<option value="">-- 에러 발생 (재시도: 🔄) --</option>';
    }
}

function syncJudgeModelSelect() {
    const select = document.getElementById('select-judge-model');
    const input = document.getElementById('stress-judgemodel');
    if (select.value) {
        input.value = select.value;
    }
}

async function saveJudgeModel() {
    const judgeModel = document.getElementById('stress-judgemodel').value.trim();
    if (!judgeModel) {
        alert("판정관 모델 이름을 입력해주세요.");
        return;
    }
    await updateConfig({ default_judge_model: judgeModel });
    showToast();
}

async function openGlobalSettings() {
    try {
        const resp = await fetch('/api/config');
        const data = await resp.json();
        
        document.getElementById('set-vault-dir').value = data.vault_dir;
        document.getElementById('set-bitnet-dir').value = data.bit_vault_dir;
        document.getElementById('set-judge-model').value = data.default_judge_model;
        
        document.getElementById('modal-settings').classList.add('active');
    } catch(e) {
        alert("설정을 읽어오지 못했습니다.");
    }
}

async function saveGlobalSettings() {
    const vault = document.getElementById('set-vault-dir').value.trim();
    const bitnet = document.getElementById('set-bitnet-dir').value.trim();
    const judge = document.getElementById('set-judge-model').value.trim();
    
    if (!vault || !bitnet || !judge) {
        alert("모든 설정 값을 기입해 주세요.");
        return;
    }

    await updateConfig({
        vault_dir: vault,
        bit_vault_dir: bitnet,
        default_judge_model: judge
    });

    document.getElementById('stress-judgemodel').value = judge;
    closeModal('settings');
    showToast();
}

async function updateConfig(payload) {
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } catch(e) {
        console.error("Config update failed", e);
    }
}

function showToast() {
    const toast = document.getElementById('toast');
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 2000);
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
        
        const chatInput = document.getElementById('chat-input');
        const chatSendBtn = document.getElementById('chat-send-btn');

        if (data.boot_status === 'ONLINE') {
            statusDot.classList.add('online');
            statusText.innerText = `온라인 - 커널 동작중 [${data.boot_message}]`;
            
            document.getElementById('btn-boot').disabled = true;
            document.getElementById('btn-shutdown').disabled = false;
            
            currentActiveModel = data.last_booted_model;
            document.getElementById('active-model-display').innerText = currentActiveModel || "모델 미선택";
            document.getElementById('active-model-display').style.color = "var(--accent)";

            if (chatInput) {
                chatInput.disabled = false;
                chatInput.placeholder = "질문을 입력하세요...";
            }
            if (chatSendBtn) {
                chatSendBtn.disabled = false;
            }
        } else if (data.boot_status === 'BOOTING') {
            statusDot.classList.add('booting');
            statusText.innerText = `가동중 - 커널 격리 공간 준비 중...`;
            
            document.getElementById('btn-boot').disabled = true;
            document.getElementById('btn-shutdown').disabled = true;

            if (chatInput) {
                chatInput.disabled = true;
                chatInput.placeholder = "⏳ 커널 가동 및 웜업 중... 잠시만 기다려주세요.";
            }
            if (chatSendBtn) {
                chatSendBtn.disabled = true;
            }
        } else if (data.boot_status === 'ERROR') {
            statusDot.classList.add('offline');
            statusText.innerText = `장애발생 - ${data.boot_message}`;
            
            document.getElementById('btn-boot').disabled = false;
            document.getElementById('btn-shutdown').disabled = true;

            if (chatInput) {
                chatInput.disabled = true;
                chatInput.placeholder = "커널이 장애 상태입니다. 재부팅해 주세요.";
            }
            if (chatSendBtn) {
                chatSendBtn.disabled = true;
            }
        } else {
            statusText.innerText = `오프라인 - 커널 동작 정지 상태`;
            document.getElementById('btn-boot').disabled = false;
            document.getElementById('btn-shutdown').disabled = true;

            if (currentActiveModel) {
                document.getElementById('active-model-display').innerText = `${currentActiveModel} (대기중)`;
                document.getElementById('active-model-display').style.color = "var(--warn)";
            } else {
                document.getElementById('active-model-display').innerText = "미선택 (OFFLINE)";
                document.getElementById('active-model-display').style.color = "var(--text-muted)";
            }

            if (chatInput) {
                chatInput.disabled = true;
                chatInput.placeholder = "커널이 가동 상태(ONLINE)일 때만 대화가 가능합니다.";
            }
            if (chatSendBtn) {
                chatSendBtn.disabled = true;
            }
        }

        const runBtn = document.getElementById('btn-run');
        if (data.boot_status === 'ONLINE') {
            if (data.benchmark_running || data.chat_running) {
                runBtn.disabled = true;
                runBtn.innerText = "⏳ RUNNING TASK...";
            } else {
                runBtn.disabled = false;
                runBtn.innerText = "⚡ RUN BENCHMARK";
            }
        } else if (data.boot_status === 'BOOTING') {
            runBtn.disabled = true;
            runBtn.innerText = "⏳ 커널 가동 중...";
        } else {
            runBtn.disabled = true;
            runBtn.innerText = "⚡ RUN BENCHMARK (커널 가동 필요)";
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
            document.getElementById('log-viewport-sys').innerHTML = ''; 
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
        
        const categories = {};
        data.models.forEach(m => {
            if (!categories[m.category]) categories[m.category] = [];
            categories[m.category].push(m);
        });

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

                const right = document.createElement('div');
                right.className = 'model-card-actions';

                if (model.unregistered) {
                    const regBtn = document.createElement('button');
                    regBtn.className = 'btn';
                    regBtn.style.backgroundColor = 'var(--warn)';
                    regBtn.style.borderColor = 'var(--warn)';
                    regBtn.style.color = 'white';
                    regBtn.innerText = "➕ 등록하기";
                    regBtn.onclick = () => openRegisterModelModal(model);
                    right.appendChild(regBtn);
                } else {
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
                }

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
            loadGalleryModels();
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
        tdId.innerText = task.task_id;
        tdId.style.fontWeight = '700';
        tdId.style.color = '#fff';
        tr.appendChild(tdId);

        const tdPrompt = document.createElement('td');
        tdPrompt.innerText = task.prompt;
        tdPrompt.style.whiteSpace = 'nowrap';
        tdPrompt.style.overflow = 'hidden';
        tdPrompt.style.textOverflow = 'ellipsis';
        tdPrompt.style.maxWidth = '320px';
        tr.appendChild(tdPrompt);

        const tdRegex = document.createElement('td');
        tdRegex.innerText = task.expected_regex || "-";
        tr.appendChild(tdRegex);

        const tdEval = document.createElement('td');
        tdEval.innerText = task.eval_type;
        tdEval.style.color = task.eval_type === 'llm_judge' ? '#60a5fa' : '#34d399';
        tr.appendChild(tdEval);

        const tdActions = document.createElement('td');
        tdActions.style.textAlign = 'center';
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
        task_id: idInput.value.trim(),
        prompt: promptInput.value.trim(),
        eval_type: evalInput.value,
        expected_regex: evalInput.value === 'regex' ? regexInput.value.trim() : ""
    };

    harnessTasks.push(task);
    renderHarnessTable();

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
            alert("SQLite 데이터베이스에 정상 동기화되었습니다.");
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
    
    // 아코디언이 닫혀있어도 값을 읽어옴
    const temp = parseFloat(document.getElementById('stress-temp').value);
    const penalty = parseFloat(document.getElementById('stress-penalty').value);
    const sysPrompt = document.getElementById('stress-sysprompt').value;
    
    const judgeModel = document.getElementById('stress-judgemodel').value.trim();

    if (!currentActiveModel) {
        alert("실행할 액티브 모델을 먼저 선택해주세요!");
        openModelGallery();
        return;
    }

    document.getElementById('log-viewport-sys').innerHTML = '';
    document.getElementById('log-viewport-bench').innerHTML = '';
    document.getElementById('log-viewport-stream').innerHTML = '';
    
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
    appendChatBubble(prompt, 'user');
    activeAiBubble = appendChatBubble("⏳ AI 추론 중…", 'ai');
    
    document.getElementById('log-viewport-stream').innerHTML = ''; 
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
        activeAiBubble.innerText = `❌ 통신 장애 발생`;
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
// Reports SQLite History View
// ─────────────────────────────────────────────────────────────────────────────

async function loadReports() {
    const tbody = document.getElementById('reports-table-body');
    tbody.innerHTML = "<tr><td colspan='10' style='text-align:center;'>조회 중...</td></tr>";
    
    try {
        const resp = await fetch('/api/reports');
        const data = await resp.json();
        
        tbody.innerHTML = "";
        if (data.length === 0) {
            tbody.innerHTML = "<tr><td colspan='10' style='text-align: center; color: var(--text-muted);'>리포트 이력이 없습니다.</td></tr>";
            return;
        }

        data.forEach(r => {
            const tr = document.createElement('tr');
            
            const timestamp = r.timestamp || "-";
            const model = r.model_name || "-";
            const engine = r.engine_type || "-";
            const mode = r.run_mode || "-";
            const count = r.task_count || 0;
            const ttft = r.avg_ttft ? `${r.avg_ttft.toFixed(1)} ms` : "-";
            const tps = r.avg_tps ? `${r.avg_tps.toFixed(2)} t/s` : "-";
            const watts = r.avg_power ? `${r.avg_power.toFixed(1)} W` : "-";
            const score = r.avg_score ? `${r.avg_score.toFixed(2)}` : "-";
            
            tr.innerHTML = `
                <td>${timestamp}</td>
                <td style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:140px;" title="${model}">${model}</td>
                <td>${engine}</td>
                <td>${mode}</td>
                <td style="text-align:center;">${count}</td>
                <td>${ttft}</td>
                <td>${tps}</td>
                <td>${watts}</td>
                <td style="font-weight:700; color:var(--accent);">${score}</td>
                <td style="text-align: center;">
                    <button class="btn" style="padding:4px 8px; font-size:11px;" onclick="viewReportDetail(${r.id})">👁️ 상세보기</button>
                    <button class="btn btn-primary" style="padding:4px 8px; font-size:11px;" onclick="exportSingleWord(${r.id})">Word</button>
                    <button class="btn btn-accent" style="padding:4px 8px; font-size:11px;" onclick="exportSingleExcel(${r.id})">Excel</button>
                    <button class="btn btn-danger" style="padding:4px 8px; font-size:11px;" onclick="deleteReport(${r.id})">🗑️</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = "<tr><td colspan='10' style='text-align: center; color: var(--danger);'>로드 실패</td></tr>";
    }
}

async function viewReportDetail(runId) {
    try {
        const resp = await fetch(`/api/reports/${runId}`);
        const data = await resp.json();
        
        const run = data.run;
        const results = data.results;
        
        document.getElementById('detail-modal-title').innerText = `📊 벤치마크 상세 보고서 [ID: ${run.id}]`;
        
        const metaDiv = document.getElementById('detail-run-meta');
        metaDiv.innerHTML = `
            <div><strong>모델명:</strong> ${run.model_name}</div>
            <div><strong>엔진/모드:</strong> ${run.engine_type} / ${run.run_mode}</div>
            <div><strong>자원 설정:</strong> Cores=${run.cpu_cores} | RAM=${run.ram_mb}MB | GPU Layers=${run.gpu_layers}</div>
            <div><strong>측정 일시:</strong> ${run.timestamp}</div>
            <div><strong>튜닝 변수:</strong> Threads=${run.threads} | n_ctx=${run.n_ctx} | Temp=${run.temperature}</div>
            <div><strong>판정관 모델:</strong> ${run.judge_model}</div>
        `;
        
        const tbody = document.getElementById('detail-results-tbody');
        tbody.innerHTML = "";
        currentDetailedResults = results;
        
        results.forEach((res, index) => {
            const tr = document.createElement('tr');
            
            // 특수한 점수(PASS/FAIL) 색상 표시
            let scoreColor = "var(--text-primary)";
            if (res.judge_score.includes("PASS")) scoreColor = "var(--accent)";
            else if (res.judge_score.includes("FAIL")) scoreColor = "var(--danger)";
            else if (!isNaN(parseFloat(res.judge_score))) {
                const s = parseFloat(res.judge_score);
                if (s >= 8) scoreColor = "var(--accent)";
                else if (s <= 4) scoreColor = "var(--danger)";
            }

            tr.innerHTML = `
                <td style="font-weight:700;">${res.task_name}</td>
                <td>${res.category}</td>
                <td>${res.ttft_ms.toFixed(1)} ms</td>
                <td>${res.tps.toFixed(2)} t/s</td>
                <td>${res.avg_gpu_w.toFixed(1)} W</td>
                <td style="font-weight:700; color:${scoreColor};">${res.judge_score}</td>
                <td>
                    <button class="btn" style="padding:2px 6px; font-size:11px;" onclick="showTaskDetail(${index})">👁️ 검사</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        // Footer Buttons Event binding
        document.getElementById('detail-btn-word').onclick = () => exportSingleWord(run.id);
        document.getElementById('detail-btn-excel').onclick = () => exportSingleExcel(run.id);
        
        document.getElementById('modal-report-detail').classList.add('active');
    } catch(e) {
        console.error(e);
        alert("상세 데이터를 가져오지 못했습니다.");
    }
}

function showTaskDetail(index) {
    const res = currentDetailedResults[index];
    if (!res) return;
    
    document.getElementById('task-detail-prompt').innerText = res.prompt_text || "";
    document.getElementById('task-detail-response').innerText = res.response_text || "";
    document.getElementById('task-detail-reason').innerText = res.judge_reason || "";
    
    document.getElementById('modal-task-detail').classList.add('active');
}

async function deleteReport(runId) {
    if (!confirm("해당 벤치마크 이력을 데이터베이스에서 삭제하시겠습니까? (복구 불가능)")) return;
    try {
        const resp = await fetch(`/api/reports/${runId}`, { method: 'DELETE' });
        if (resp.ok) {
            loadReports();
        }
    } catch(e) {
        alert("삭제 실패");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// EXCEL & WORD EXPORTS DOWNLOAD
// ─────────────────────────────────────────────────────────────────────────────

function exportFullExcel() {
    window.open('/api/reports/export/excel', '_blank');
}

function exportSingleExcel(runId) {
    window.open(`/api/reports/export/excel?run_id=${runId}`, '_blank');
}

async function exportSingleWord(runId) {
    const useLlm = document.getElementById('report-llm-summary').checked;
    
    // 파일 다운로드 중이라는 피드백 제공 (LLM 동작 시 수 초 소요될 수 있음)
    const toast = document.getElementById('toast');
    toast.innerText = "📝 Word 보고서 생성 및 AI 요약 분석 중…";
    toast.style.backgroundColor = "var(--warn)";
    toast.style.display = 'block';

    try {
        const resp = await fetch('/api/reports/export/word', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                run_id: runId,
                use_llm_summary: useLlm
            })
        });
        
        toast.style.display = 'none';
        
        if (resp.ok) {
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `AMEVA_Report_Run_${runId}.docx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            alert("보고서 생성 실패");
        }
    } catch (e) {
        toast.style.display = 'none';
        alert("네트워크 장애로 보고서를 다운로드할 수 없습니다.");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// UI Helpers & Navigation
// ─────────────────────────────────────────────────────────────────────────────

function switchTab(tabId) {
    activeTab = tabId;
    
    const btns = document.querySelectorAll('.nav-tabs .tab-btn');
    btns.forEach(btn => {
        if (btn.getAttribute('onclick').includes(tabId)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

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

function toggleAccordion() {
    const body = document.getElementById('accordion-body');
    const arrow = document.getElementById('accordion-arrow');
    body.classList.toggle('open');
    if (body.classList.contains('open')) {
        arrow.innerText = '▲';
    } else {
        arrow.innerText = '▼';
    }
}

// String Helper Escapes
function escapeHtml(text) {
    if (!text) return "";
    return text
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;")
         .replace(/`/g, "\\`")
         .replace(/\n/g, "\\n")
         .replace(/\r/g, "\\r");
}

function unescapeHtml(text) {
    if (!text) return "";
    return text
         .replace(/\\n/g, "\n")
         .replace(/\\r/g, "\r")
         .replace(/\\`/g, "`")
         .replace(/&lt;/g, "<")
         .replace(/&gt;/g, ">")
         .replace(/&quot;/g, '"')
         .replace(/&#039;/g, "'")
         .replace(/&amp;/g, "&");
}

function openRegisterModelModal(model = null) {
    const titleEl = document.getElementById('register-modal-title');
    const idInput = document.getElementById('reg-model-id');
    const nameInput = document.getElementById('reg-display-name');
    const catSelect = document.getElementById('reg-category');
    const tagInput = document.getElementById('reg-tag');
    const descText = document.getElementById('reg-description');
    const ramInput = document.getElementById('reg-min-ram-gb');
    const sizeInput = document.getElementById('reg-size-gb');
    const fileInput = document.getElementById('reg-filename');
    const ollamaInput = document.getElementById('reg-ollama-tag');
    const urlInput = document.getElementById('reg-hf-url');

    // Reset readonly status
    idInput.readOnly = false;
    fileInput.readOnly = false;
    ollamaInput.readOnly = false;

    if (!model) {
        titleEl.innerText = "➕ 기타 모델 직접 등록";
        idInput.value = "";
        nameInput.value = "";
        catSelect.value = "Medium";
        tagInput.value = "";
        descText.value = "";
        ramInput.value = "4.0";
        sizeInput.value = "0.0";
        fileInput.value = "";
        ollamaInput.value = "";
        urlInput.value = "";
    } else {
        titleEl.innerText = "➕ 미등록 모델 등록";
        
        // Clean up temporary ID prefix if present
        let cleanId = model.id;
        if (cleanId.startsWith("ext-gguf-")) cleanId = cleanId.substring(9);
        if (cleanId.startsWith("ext-ollama-")) cleanId = cleanId.substring(11);
        
        idInput.value = cleanId;
        nameInput.value = model.display.replace(".gguf", "");
        catSelect.value = model.category || "Medium";
        tagInput.value = "📦 외부 등록 모델";
        descText.value = model.desc || "";
        ramInput.value = model.min_ram_gb || "4.0";
        sizeInput.value = model.size_gb || "0.0";
        fileInput.value = model.filename || "";
        ollamaInput.value = model.ollama_tag || "";
        urlInput.value = model.hf_url || "";

        // Make filename or ollama_tag readonly if they are pre-populated
        if (model.filename) {
            fileInput.readOnly = true;
        }
        if (model.ollama_tag) {
            ollamaInput.readOnly = true;
        }
    }

    document.getElementById('modal-model-register').classList.add('active');
}

async function submitModelRegistration() {
    const idInput = document.getElementById('reg-model-id');
    const nameInput = document.getElementById('reg-display-name');
    const catSelect = document.getElementById('reg-category');
    const tagInput = document.getElementById('reg-tag');
    const descText = document.getElementById('reg-description');
    const ramInput = document.getElementById('reg-min-ram-gb');
    const sizeInput = document.getElementById('reg-size-gb');
    const fileInput = document.getElementById('reg-filename');
    const ollamaInput = document.getElementById('reg-ollama-tag');
    const urlInput = document.getElementById('reg-hf-url');

    const modelId = idInput.value.trim();
    const displayName = nameInput.value.trim();
    const filename = fileInput.value.trim();
    const ollamaTag = ollamaInput.value.trim();

    if (!modelId || !displayName) {
        alert("모델 고유 ID와 표시용 이름을 입력해 주세요.");
        return;
    }

    // 간단한 ID 검증 (공백 없어야 함 등)
    if (!/^[a-zA-Z0-9\-_.]+$/.test(modelId)) {
        alert("모델 고유 ID는 영문자, 숫자, 하이픈(-), 언더바(_), 마침표(.)만 포함해야 합니다.");
        return;
    }

    if (!filename && !ollamaTag) {
        alert("GGUF 파일명 또는 Ollama 태그 중 최소 하나는 입력해야 사용이 가능합니다.");
        return;
    }

    const payload = {
        model_id: modelId,
        display_name: displayName,
        category: catSelect.value,
        tag: tagInput.value.trim(),
        description: descText.value.trim(),
        min_ram_gb: parseFloat(ramInput.value) || 2.0,
        size_gb: parseFloat(sizeInput.value) || 0.0,
        filename: filename,
        ollama_tag: ollamaTag,
        hf_url: urlInput.value.trim()
    };

    try {
        const resp = await fetch('/api/models/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            alert(`모델 등록 성공: ${modelId}`);
            closeModal('model-register');
            // 리로드
            await loadGalleryModels();
        } else {
            const err = await resp.json();
            alert(`등록 실패: ${err.detail || '알 수 없는 오류'}`);
        }
    } catch (e) {
        alert(`네트워크 통신 오류: ${e}`);
    }
}
