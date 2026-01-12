// air_logic.js - Velox Air Specialized Web Client (Passive & Eco Optimized)

class Logger {
    constructor(name) { this.name = name; }
    _log(level, message, ...args) {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`%c[${timestamp}] ${this.name} | ${level}: ${message}`, this._getColor(level), ...args);
    }
    _getColor(level) {
        switch (level) {
            case 'DEBUG': return 'color: #71717a;';
            case 'INFO': return 'color: #06b6d4;'; 
            case 'WARN': return 'color: #f59e0b;';
            case 'ERROR': return 'color: #ef4444; font-weight: bold;';
            default: return '';
        }
    }
    debug(message, ...args) { this._log('DEBUG', message, ...args); }
    info(message, ...args) { this._log('INFO', message, ...args); }
    warn(message, ...args) { this._log('WARN', message, ...args); }
    error(message, ...args) { this._log('ERROR', message, ...args); }
}

const logger = new Logger('Velox Air');

// Multi-language Dictionary
const i18n = {
    zh_TW: {
        scaling_auto: "畫面適應：自動",
        scaling_fill: "畫面適應：填滿",
        scaling_stretch: "畫面適應：拉伸",
        control_on: "遠端控制：開啟",
        control_off: "遠端控制：關閉",
        fullscreen: "全螢幕",
        eco_active: "省電模式執行中",
        super_eco: "超級省電模式已啟動 (10 FPS)",
        stream_active: "節能串流已啟動",
        reconnecting: "正在嘗試重新連線...",
        check_server: "請檢查伺服器狀態",
        ready_mirror: "準備鏡像",
        scanning: "專為舊型硬體優化。正在掃描區域網路中的 Velox 伺服器...",
        start_monitoring: "開始監測",
        offline: "尚未連線",
        passive_hint: "伴侶顯示模式已啟動",
        footer: "♻️ 舊硬體再生 | Velox Air 節能版",
        reset_initiated: "系統正在自動修復中...",
        reset_recovering: "正在清理快取緩衝並重設驅動程序鎖定",
        reset_manual: "手動解除遮罩",
        confirm_reset: "是否要重設所有串流引擎並清除驅動程序鎖定？",
        waiting_engine: "正在進行初始化擷取...",
        sys_log_ready: "[系統] 控制中心已啟動。",
        help_title: "使用說明",
        help_tip1: "Air 模式專為舊平板設計，預設鎖定 20 FPS 以節省電力。",
        help_tip2: "若電池電量低於 20%，系統會自動進入「超級省電模式」。",
        help_tip3: "點擊「全螢幕」或將網頁加入主畫面可獲得最佳體驗。",
        hd_badge: "高清"
    },
    en: {
        scaling_auto: "Fit: Contain",
        scaling_fill: "Fit: Cover",
        scaling_stretch: "Fit: Stretch",
        control_on: "Control: ON",
        control_off: "Control: OFF",
        fullscreen: "Fullscreen",
        eco_active: "Eco Mode Active",
        super_eco: "SUPER ECO ACTIVE (10 FPS)",
        stream_active: "Eco Stream Active",
        reconnecting: "Reconnecting...",
        check_server: "Check Server Status",
        ready_mirror: "Ready to Mirror",
        scanning: "Optimized for legacy hardware. Scanning for Velox server...",
        start_monitoring: "Start Monitoring",
        offline: "Offline",
        passive_hint: "Passive Display Active",
        footer: "♻️ Legacy Reclaimed | Velox Air Tier",
        reset_initiated: "System Recovering...",
        reset_recovering: "Purging buffers and clearing driver locks",
        reset_manual: "Dismiss Manually",
        confirm_reset: "Reset all engine states and clear driver locks?",
        waiting_engine: "Initial Capture...",
        sys_log_ready: "[SYSTEM] Controller initialized.",
        help_title: "Instructions",
        help_tip1: "Air mode is optimized for legacy tablets, capped at 20 FPS to save battery.",
        help_tip2: "If battery drops below 20%, 'Super Eco Mode' will engage automatically.",
        help_tip3: "Use 'Add to Home Screen' or the Fullscreen button for the best experience.",
        hd_badge: "HD"
    }
};

let currentLang = 'en';

function detectLanguage() {
    const browserLang = navigator.language || navigator.userLanguage || 'en';
    if (browserLang.toLowerCase().includes('zh')) return 'zh_TW';
    return 'en';
}

// Initialize with auto-detection
currentLang = detectLanguage();

function t(key) {
    return i18n[currentLang][key] || key;
}

function updateUILanguage() {
    // Update static elements if they exist
    const setTxt = (id, key) => { const el = document.getElementById(id); if(el) el.textContent = t(key); };

    setTxt('setupTitle', 'ready_mirror');
    setTxt('setupDesc', 'scanning');
    setTxt('connectBtn', 'start_monitoring');
    setTxt('connectionStatus', 'offline');
    setTxt('passiveHint', 'passive_hint');
    setTxt('footerText', 'footer');
    setTxt('fullscreenBtn', 'fullscreen');
    setTxt('hdBadge', 'hd_badge');
    
    // Help Modal
    setTxt('helpTitle', 'help_title');
    setTxt('helpTip1', 'help_tip1');
    setTxt('helpTip2', 'help_tip2');
    setTxt('helpTip3', 'help_tip3');
    
    // Recovery Overlay
    const overlay = document.getElementById('recoveryOverlay');
    if (overlay) {
        // Use more robust selectors for overlay text
        const titleEl = overlay.querySelector('div:nth-of-type(2)');
        const descEl = overlay.querySelector('div:nth-of-type(3)');
        const btnEl = overlay.querySelector('button');
        if(titleEl) titleEl.textContent = t('reset_initiated');
        if(descEl) descEl.textContent = t('reset_recovering');
        if(btnEl) btnEl.textContent = t('reset_manual');
    }

    // Dashboard placeholders
    setTxt('snapshotPlaceholder', 'waiting_engine');

    // Dynamic state buttons
    const scalingBtn = document.getElementById('scalingBtn');
    if (scalingBtn) {
        if (scalingMode === 'contain') scalingBtn.textContent = t('scaling_auto');
        else if (scalingMode === 'cover') scalingBtn.textContent = t('scaling_fill');
        else scalingBtn.textContent = t('scaling_stretch');
    }

    const controlToggleBtn = document.getElementById('controlToggleBtn');
    if (controlToggleBtn) {
        controlToggleBtn.textContent = controlEnabled ? t('control_on') : t('control_off');
    }

    // Battery / Eco Badges (Update their content if they aren't empty)
    const ecoBadge = document.getElementById('ecoBadge');
    if (ecoBadge && ecoBadge.textContent !== "") {
        ecoBadge.textContent = isEcoThrottled ? t('super_eco') : t('eco_active');
    }
}

// Global State
const IS_HTTPS = window.location.protocol === 'https:';
const WS_PROTOCOL = IS_HTTPS ? 'wss:' : 'ws:';
// Port mapping:
// HTTPS (8080) -> WSS (8765)
// HTTP (8081)  -> WS  (8766)
// HTTP (8080)  -> WS  (8765) [Fallback when no SSL certs exist]
const WS_PORT = IS_HTTPS ? 8765 : (window.location.port == '8081' ? 8766 : 8765);
const WS_URL = `${WS_PROTOCOL}//${window.location.hostname}:${WS_PORT}`;

let ws = null;
let renderer = null;
let frameBuffer = null;
let jitterBuffer = [];
let isEcoThrottled = false;
let controlEnabled = false;
let wakeLock = null;
let scalingMode = 'contain'; // contain, cover, stretch
const JITTER_BUFFER_SIZE = 4; 

// Device Identity
function getDeviceName() {
    const ua = navigator.userAgent;
    if (/iPad|iPhone|iPod/.test(ua)) return "Apple Device";
    if (/Android/.test(ua)) return "Android Tablet";
    if (/Windows/.test(ua)) return "Windows PC";
    if (/Macintosh/.test(ua)) return "Mac Device";
    if (/Linux/.test(ua)) return "Linux Device";
    return "Web Companion";
}
const DEVICE_NAME = getDeviceName();

// Compatibility Flags
const HAS_CREATE_IMAGE_BITMAP = typeof window.createImageBitmap === 'function';

async function requestWakeLock() {
    if ('wakeLock' in navigator) {
        try {
            wakeLock = await navigator.wakeLock.request('screen');
            logger.info("Screen Wake Lock acquired");
            wakeLock.onrelease = () => logger.info("Screen Wake Lock released");
        } catch (err) {
            logger.warn(`Wake Lock Error: ${err.message}`);
        }
    }
}

function releaseWakeLock() {
    if (wakeLock) {
        wakeLock.release();
        wakeLock = null;
    }
}

const stats = {
    framesDecoded: 0,
    totalDecodeTime: 0,
    lastReportTime: performance.now(),
    fps: 0,
    batteryLevel: 100,
    isCharging: true
};

// Parallel Decoder Worker Pool
class DecoderPool {
    constructor(size = Math.min(navigator.hardwareConcurrency || 2, 4)) {
        this.workers = [];
        this.callbacks = new Map();
        this.msgId = 0;
        this.index = 0;
        
        // Calculate stable worker path
        const scriptPath = document.querySelector('script[src*="air_logic.js"]').src;
        const workerUrl = scriptPath.replace('air_logic.js', 'decoder_worker.js');
        logger.info(`Initializing DecoderPool with worker: ${workerUrl}`);

        for (let i = 0; i < size; i++) {
            const worker = new Worker(workerUrl);
            worker.onmessage = (e) => {
                const { id, error, ...data } = e.data;
                const cb = this.callbacks.get(id);
                if (cb) {
                    this.callbacks.delete(id);
                    clearTimeout(cb.timeout); // Clear the fail-safe
                    if (error) cb.reject(error); else {
                        const decodeEnd = performance.now();
                        stats.totalDecodeTime += (decodeEnd - cb.startTime);
                        cb.resolve(data);
                    }
                }
            };
            this.workers.push(worker);
        }
    }
    decode(tileData, x, y, width, height, isFull) {
        return new Promise((resolve, reject) => {
            const id = this.msgId++;
            const startTime = performance.now();
            const worker = this.workers[this.index];
            this.index = (this.index + 1) % this.workers.length;
            
            // Fail-safe: Timeout if worker hangs
            const timeout = setTimeout(() => {
                if (this.callbacks.has(id)) {
                    this.callbacks.delete(id);
                    // Reset worker to clear bad state? For now just reject.
                    reject(new Error("Decoder Timeout"));
                }
            }, 2000);

            this.callbacks.set(id, { resolve, reject, startTime, timeout });
            worker.postMessage({ id, tileData, x, y, width, height, isFull }, [tileData.buffer]);
        });
    }
}
const decoderPool = new DecoderPool();

function sendClientStats() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const now = performance.now();
    const duration = (now - stats.lastReportTime) / 1000;
    stats.fps = stats.framesDecoded / duration;
    
    const statsPayload = {
        type: 'CLIENT_STATS',
        device_name: DEVICE_NAME,
        fps: Math.round(stats.fps),
        avg_decode_ms: stats.framesDecoded > 0 ? parseFloat((stats.totalDecodeTime / stats.framesDecoded).toFixed(2)) : 0,
        pending_tiles: jitterBuffer.length,
        battery: stats.batteryLevel,
        is_charging: stats.isCharging,
        mode: isEcoThrottled ? 'SUPER_ECO' : 'AIR_NORMAL',
        timestamp: Date.now()
    };
    ws.send(JSON.stringify(statsPayload));
    stats.framesDecoded = 0;
    stats.totalDecodeTime = 0;
    stats.lastReportTime = now;
}

function updateScaling() {
    const videoCanvas = document.getElementById('videoCanvas');
    if (!videoCanvas) return;
    
    // Ensure canvas is set to fill container, then let object-fit do its magic
    videoCanvas.style.width = '100%';
    videoCanvas.style.height = '100%';

    if (scalingMode === 'contain') {
        videoCanvas.style.objectFit = 'contain';
    } else if (scalingMode === 'cover') {
        videoCanvas.style.objectFit = 'cover';
    } else if (scalingMode === 'stretch') {
        videoCanvas.style.objectFit = 'fill';
    }
}

setInterval(sendClientStats, 2000); 

class CanvasRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d', { alpha: false });
        this.currentWidth = 0;
        this.currentHeight = 0;
    }
    resize(width, height) {
        if (this.currentWidth === width && this.currentHeight === height) return;
        this.canvas.width = width;
        this.canvas.height = height;
        this.currentWidth = width;
        this.currentHeight = height;
    }
    updateTile(bitmap, x, y) {
        // Apply brightness filter based on battery
        if (!stats.isCharging && stats.batteryLevel < 30) {
            this.ctx.filter = 'brightness(0.7)';
        } else {
            this.ctx.filter = 'none';
        }
        this.ctx.drawImage(bitmap, x, y);
    }
    render() { }
}

class FrameBuffer {
    constructor(width, height) {
        this.width = width; this.height = height;
        this.offscreenCanvas = document.createElement('canvas');
        this.renderer = new CanvasRenderer(this.offscreenCanvas);
        this.renderer.resize(width, height);
    }
    async processTiles(tiles) {
        // Wrap individual decodes to prevent one failure from killing the frame
        const results = await Promise.all(tiles.map(async t => {
            try {
                return await decoderPool.decode(t.data, t.x, t.y, t.w, t.h, t.isFull);
            } catch (e) {
                // Log but return null so other tiles can render
                // logger.debug("Tile decode failed", e); 
                return null;
            }
        }));

        for (const res of results) {
            if (!res) continue; // Skip failed tiles

            if (res.bitmap) {
                if (res.isFull) this.renderer.resize(res.width, res.height);
                this.renderer.updateTile(res.bitmap, res.x, res.y);
                res.bitmap.close();
            } else if (res.blob) {
                // FALLBACK PATH: Use Image element
                await new Promise((resolve) => {
                    const img = new Image();
                    img.onload = () => {
                        if (res.isFull) this.renderer.resize(res.width, res.height);
                        this.renderer.updateTile(img, res.x, res.y);
                        URL.revokeObjectURL(img.src);
                        resolve();
                    };
                    img.src = URL.createObjectURL(res.blob);
                });
            }
        }
    }
    getFrame() { return this.offscreenCanvas; }
}

async function connect() {
    const setupSection = document.getElementById('setupSection');
    const videoCanvas = document.getElementById('videoCanvas');
    const statusText = document.getElementById('connectionStatus');

    try {
        ws = new WebSocket(WS_URL);
        ws.binaryType = 'arraybuffer';
        ws.onopen = () => {
            logger.info("Velox Air Connected");
            try {
                localStorage.setItem('velox_air_autoconnect', 'true');
            } catch (e) { logger.warn("Storage blocked by browser settings"); }
            
            statusText.textContent = t('stream_active');
            setupSection.style.display = 'none';
            videoCanvas.style.display = 'block';
            document.getElementById('passiveHint').style.display = 'block';
            
            requestWakeLock();
            requestAnimationFrame(processJitterBuffer);
        };
        ws.onmessage = async (event) => {
            if (typeof event.data === 'string') {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'VERSION') {
                        logger.info(`Server Version: ${msg.version} | Monitor: ${msg.monitor_id} | Lang: ${msg.language}`);
                        if (msg.language && msg.language !== 'auto') {
                            currentLang = msg.language;
                        } else {
                            currentLang = detectLanguage();
                        }
                        updateUILanguage();
                    }
                } catch(e) {}
                return;
            }
            try {
                await processBinaryPayload(event.data);
            } catch (e) {
                logger.error("Frame processing error", e);
            }
        };
        ws.onclose = () => {
            logger.warn("Server disconnected.");
            statusText.textContent = t('reconnecting');
            setupSection.style.display = 'flex';
            videoCanvas.style.display = 'none';
            document.getElementById('passiveHint').style.display = 'none';
            
            releaseWakeLock();
            setTimeout(connect, 3000);
        };
    } catch (e) { 
        logger.error("Connection failed", e); 
        statusText.textContent = t('check_server');
    }
}

async function processBinaryPayload(arrayBuffer) {
    const view = new DataView(arrayBuffer);
    const type = view.getUint8(0);
    
    // 0x01: Normal, 0x02: Static Enhancement
    if (type !== 0x01 && type !== 0x02) return; 

    const isLossless = (type === 0x02);
    if (isLossless) {
        logger.info("✨ Received Static Enhancement (Lossless)");
        const hd = document.getElementById('hdBadge');
        if (hd) {
            hd.classList.remove('hidden');
            setTimeout(() => hd.classList.add('hidden'), 3000);
        }
    }

    const timestampRaw = view.getBigInt64(1, true);
    let timestamp;
    
    // Heuristic: If Int64 is absurdly large/small, it's probably a Float64 (Native Pipeline)
    // Legacy timestamp is roughly 1.7e12 (ms) or 1.7e15 (us)
    // Float64 for 2026 is roughly 1.7e9 (sec) or 1.7e12 (ms)
    // If we interpret Float64 1.7e9 as BigInt, it looks like a random huge number.
    if (timestampRaw > 2000000000000000n || timestampRaw < 0n) {
        timestamp = view.getFloat64(1, true);
    } else {
        timestamp = Number(timestampRaw) / 1000.0;
    }

    // Ensure timestamp is in SECONDS for drawFrame
    // If it's still in ms ( > 1e11), convert to sec
    if (timestamp > 1000000000000) timestamp /= 1000.0;

    const numTiles = view.getInt32(9, true);

    let offset = 13;
    let tiles = [];

    if (numTiles === 0) {
        const w = view.getInt32(offset, true); offset += 4;
        const h = view.getInt32(offset, true); offset += 4;
        const len = view.getInt32(offset, true); offset += 4;
        tiles.push({ data: new Uint8Array(arrayBuffer.slice(offset, offset + len)), isFull: true, w, h, x: 0, y: 0 });
        if (!frameBuffer) frameBuffer = new FrameBuffer(w, h);
    } else {
        if (!frameBuffer) return;
        for (let i = 0; i < numTiles; i++) {
            const tx = view.getInt32(offset, true); offset += 4;
            const ty = view.getInt32(offset, true); offset += 4;
            const tw = view.getInt32(offset, true); offset += 4;
            const th = view.getInt32(offset, true); offset += 4;
            const tlen = view.getInt32(offset, true); offset += 4;
            tiles.push({ data: new Uint8Array(arrayBuffer.slice(offset, offset + tlen)), isFull: false, x: tx, y: ty, w: tw, h: th });
            offset += tlen;
        }
    }

    await frameBuffer.processTiles(tiles);
    const frameSnapshot = await createImageBitmap(frameBuffer.getFrame());
    jitterBuffer.push({ timestamp, frame: frameSnapshot, isLossless });
    
    if (jitterBuffer.length > JITTER_BUFFER_SIZE && !isLossless) {
        const d = jitterBuffer.shift(); if (d.frame) d.frame.close();
    }
}

function processJitterBuffer() {
    if (jitterBuffer.length > 0) {
        jitterBuffer.sort((a, b) => a.timestamp - b.timestamp);
        const d = jitterBuffer.shift();
        drawFrame(d.frame, d.timestamp);
        d.frame.close();
    }
    requestAnimationFrame(processJitterBuffer);
}

function drawFrame(frame, timestamp) {
    const videoCanvas = document.getElementById('videoCanvas');
    const latencyText = document.getElementById('latency');
    if (!videoCanvas) return;
    
    // Count this as a successfully displayed frame
    stats.framesDecoded++;

    if (videoCanvas.width !== frame.width || videoCanvas.height !== frame.height) {
        videoCanvas.width = frame.width; videoCanvas.height = frame.height;
    }
    const ctx = videoCanvas.getContext('2d', { alpha: false });
    ctx.drawImage(frame, 0, 0);
    const latency = Date.now() - (timestamp * 1000);
    if (latencyText) {
        // Only show if positive and reasonable (< 10s)
        if (latency >= 0 && latency < 10000) {
            latencyText.textContent = `${latency.toFixed(0)}`;
        } else {
            latencyText.textContent = "---";
        }
    }
}

function handleInput(e) {
    if (!ws || ws.readyState !== WebSocket.OPEN || !controlEnabled) return;
    const videoCanvas = document.getElementById('videoCanvas');
    const rect = videoCanvas.getBoundingClientRect();
    const scaleX = videoCanvas.width / rect.width;
    const scaleY = videoCanvas.height / rect.height;
    let x, y, it_type = 0;

    if (e.type.startsWith('touch')) {
        const touch = e.touches[0] || e.changedTouches[0];
        if (!touch) return;
        x = (touch.clientX - rect.left) * scaleX;
        y = (touch.clientY - rect.top) * scaleY;
        if (e.type === 'touchstart') it_type = 1;
        else if (e.type === 'touchend') it_type = 2;
        else it_type = 0; // touchmove
        // Prevent scrolling while touching the canvas
        if (e.cancelable) e.preventDefault();
    } else {
        x = (e.clientX - rect.left) * scaleX;
        y = (e.clientY - rect.top) * scaleY;
        if (e.type === 'mousedown') it_type = 1;
        else if (e.type === 'mouseup') it_type = 2;
        else it_type = 0; // mousemove
    }

    const buffer = new ArrayBuffer(11);
    const view = new DataView(buffer);
    view.setUint8(0, 0x03); // Mouse
    view.setUint8(1, it_type);
    view.setInt32(2, Math.round(x), true);
    view.setInt32(6, Math.round(y), true);
    view.setUint8(10, e.button || 0);
    ws.send(buffer);
}

function updateBattery() {
    const batteryText = document.getElementById('batteryStatus');
    const ecoBadge = document.getElementById('ecoBadge');
    
    if (navigator.getBattery) {
        navigator.getBattery().then(battery => {
            stats.batteryLevel = Math.round(battery.level * 100);
            stats.isCharging = battery.charging;
            batteryText.textContent = `${stats.isCharging ? '⚡' : '🔋'} ${stats.batteryLevel}%`;
            
            if (stats.batteryLevel < 20 && !stats.isCharging) {
                isEcoThrottled = true;
                ecoBadge.textContent = t('super_eco');
                ecoBadge.classList.add('bg-red-100', 'text-red-700');
                ecoBadge.classList.remove('bg-cyan-100', 'text-cyan-700');
            } else {
                isEcoThrottled = false;
                ecoBadge.textContent = t('eco_active');
                ecoBadge.classList.add('bg-cyan-100', 'text-cyan-700');
                ecoBadge.classList.remove('bg-red-100', 'text-red-700');
            }
        });
    }
}

function toggleFullscreen() {
    const doc = window.document;
    const docEl = doc.documentElement;

    const requestFullScreen = docEl.requestFullscreen || docEl.mozRequestFullScreen || docEl.webkitRequestFullScreen || docEl.msRequestFullscreen;
    const cancelFullScreen = doc.exitFullscreen || doc.mozCancelFullScreen || doc.webkitExitFullscreen || doc.msExitFullscreen;

    if (!doc.fullscreenElement && !doc.mozFullScreenElement && !doc.webkitFullscreenElement && !doc.msFullscreenElement) {
        if (requestFullScreen) {
            requestFullScreen.call(docEl).catch(e => logger.warn(`Fullscreen error: ${e.message}`));
        } else {
            logger.warn("Fullscreen API not supported");
        }
    } else {
        if (cancelFullScreen) {
            cancelFullScreen.call(doc);
        }
    }
}

function toggleHelp() {
    const modal = document.getElementById('helpModal');
    if (!modal) return;
    
    if (modal.classList.contains('hidden')) {
        modal.classList.remove('hidden');
        setTimeout(() => modal.classList.remove('opacity-0'), 10);
    } else {
        modal.classList.add('opacity-0');
        setTimeout(() => modal.classList.add('hidden'), 300);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Initial translation based on browser detection
    updateUILanguage();

    document.getElementById('connectBtn').onclick = connect;







    const scalingBtn = document.getElementById('scalingBtn');



        if (scalingBtn) {



            scalingBtn.onclick = () => {



                if (scalingMode === 'contain') {



                    scalingMode = 'cover';



                } else if (scalingMode === 'cover') {



                    scalingMode = 'stretch';



                } else {



                    scalingMode = 'contain';



                }



                updateUILanguage();



                updateScaling();



            };



        }







    const controlToggleBtn = document.getElementById('controlToggleBtn');



    const videoCanvas = document.getElementById('videoCanvas');







    if (controlToggleBtn) {



        controlToggleBtn.onclick = () => {



            controlEnabled = !controlEnabled;



            updateUILanguage();



            controlToggleBtn.classList.toggle('bg-cyan-500', controlEnabled);



            controlToggleBtn.classList.toggle('text-white', controlEnabled);



            controlToggleBtn.classList.toggle('bg-gray-100', !controlEnabled);



            controlToggleBtn.classList.toggle('text-gray-500', !controlEnabled);



        };



    }







    // Attach Input Listeners



    if (videoCanvas) {



        ['mousedown', 'mousemove', 'mouseup'].forEach(evt => {



            videoCanvas.addEventListener(evt, handleInput);



        });



        ['touchstart', 'touchmove', 'touchend'].forEach(evt => {



            videoCanvas.addEventListener(evt, handleInput, { passive: false });



        });



    }



    



    // Auto-connect if possible

    if (localStorage.getItem('velox_air_autoconnect') === 'true') {

        setTimeout(connect, 1000);

    }

    

    updateBattery();

    setInterval(updateBattery, 30000);

});
