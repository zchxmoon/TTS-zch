import os
import subprocess
import threading
import requests
import torch
import psutil
from flask import Flask, render_template_string, request, jsonify, send_file
from my_tts import (
    submit_task, get_task_status, UPLOAD_FOLDER,
    online_voices, local_voices_list
)

try:
    from advanced_tts import (
        submit_gpt_sovits_task, GPT_MODELS, SOVITS_MODELS,
        REF_AUDIOS, GSV_LITE_AVAILABLE, _engine_mode,
        check_api_service, GPT_SOVITS_API_PORT
    )
    GPT_SOVITS_AVAILABLE = True
except ImportError:
    GPT_SOVITS_AVAILABLE = False
    GSV_LITE_AVAILABLE = False
    _engine_mode = "api"
    check_api_service = None
    GPT_SOVITS_API_PORT = 9876
    GPT_MODELS = {}
    SOVITS_MODELS = {}
    REF_AUDIOS = []

app = Flask(__name__)

gpt_voice_list = [{"id": k, "name": v["name"], "version": v.get("version", "v1")} for k, v in GPT_MODELS.items()]
sovits_voice_list = [{"id": k, "name": v["name"], "version": v.get("version", "v1")} for k, v in SOVITS_MODELS.items()]

GPT_SOVITS_PATH = r"E:\GPT-SoVITS-v3lora-2025"
GPT_SOVITS_API_PORT = 9876
GPT_SOVITS_WEBUI_PORT = 9874
_api_process = None
_webui_process = None

def _get_hw_info():
    hw = {}
    try:
        if torch.cuda.is_available():
            hw["device"] = f"GPU - {torch.cuda.get_device_name(0)}"
            hw["device_icon"] = "🟢"
            hw["device_type"] = "gpu"
            hw["framework"] = f"PyTorch {torch.__version__}+cuda"
            hw["vram"] = f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB"
        else:
            hw["device"] = "CPU"
            hw["device_icon"] = "🔵"
            hw["device_type"] = "cpu"
            hw["framework"] = f"PyTorch {torch.__version__}+cpu"
            import psutil
            hw["vram"] = f"{psutil.virtual_memory().total / 1024**3:.1f} GB"
    except:
        hw["device"] = "未知"
        hw["device_icon"] = "⚪"
        hw["device_type"] = "unknown"
        hw["framework"] = torch.__version__
        hw["vram"] = "未知"
    return hw

HARDWARE_INFO = _get_hw_info()

def _check_port(port):
    try:
        r = requests.get(f"http://127.0.0.1:{port}", timeout=2)
        return r.status_code in [200, 400, 404, 405]
    except:
        return False

def _start_process(cmd, cwd=None):
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True, None
    except Exception as e:
        return False, str(e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS 语音合成</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 650px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #999;
            font-size: 13px;
            margin-bottom: 25px;
        }
        .mode-switch {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .mode-btn {
            flex: 1;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            background: white;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            color: #666;
            text-align: center;
        }
        .mode-btn.active {
            border-color: #667eea;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .mode-btn:hover:not(.active) {
            border-color: #667eea;
            color: #667eea;
        }
        .mode-desc {
            font-size: 11px;
            font-weight: normal;
            opacity: 0.8;
            margin-top: 4px;
        }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        select, textarea {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            background: white;
            transition: border-color 0.3s;
        }
        select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea {
            height: 120px;
            resize: vertical;
            font-size: 16px;
        }
        .slider-container { display: flex; align-items: center; gap: 15px; }
        input[type="range"] {
            flex: 1;
            height: 6px;
            -webkit-appearance: none;
            background: #e0e0e0;
            border-radius: 3px;
            outline: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px; height: 20px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }
        .speed-value {
            min-width: 50px;
            text-align: center;
            font-weight: bold;
            color: #667eea;
        }
        .btn-speak {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-speak:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-speak:disabled { opacity: 0.6; cursor: not-allowed; }
        .status {
            text-align: center;
            margin-top: 20px;
            padding: 10px;
            border-radius: 8px;
            display: none;
        }
        .status.success { background: #e8f5e9; color: #2e7d32; display: block; }
        .status.error { background: #ffebee; color: #c62828; display: block; }
        .status.loading { background: #e3f2fd; color: #1565c0; display: block; }
        audio { width: 100%; margin-top: 20px; display: none; }
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #e0e0e0;
            border-radius: 2px;
            margin-top: 10px;
            overflow: hidden;
            display: none;
        }
        .progress-bar.active { display: block; }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            animation: progress-animate 1.5s ease-in-out infinite;
        }
        @keyframes progress-animate {
            0% { width: 0%; }
            50% { width: 70%; }
            100% { width: 100%; }
        }
        .char-count {
            text-align: right;
            font-size: 12px;
            color: #999;
            margin-top: 5px;
        }
        .mode-hint {
            font-size: 12px;
            color: #999;
            margin-top: 5px;
            padding: 8px;
            background: #f5f5f5;
            border-radius: 6px;
        }
        .advanced-link {
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .advanced-link a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
        }
        .advanced-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>TTS 语音合成</h1>
        <p class="subtitle">支持本地离线和在线两种引擎</p>

        <div class="mode-switch">
            <button class="mode-btn active" id="modeOnline" onclick="setMode('online')">
                在线引擎
                <div class="mode-desc">edge-tts · 音质好 · 速度快</div>
            </button>
            <button class="mode-btn" id="modeLocal" onclick="setMode('local')">
                本地引擎
                <div class="mode-desc">pyttsx3 · 离线 · 无需网络</div>
            </button>
        </div>

        <div class="form-group">
            <label>语音选择</label>
            <select id="voiceSelect"></select>
        </div>

        <div class="form-group">
            <label for="text">输入文本</label>
            <textarea id="text" placeholder="请输入要朗读的文本...">你好，欢迎使用本地语音合成服务！</textarea>
            <div class="char-count">已输入 <span id="charCount">0</span> 字符</div>
        </div>

        <div class="form-group">
            <label>语速调节</label>
            <div class="slider-container">
                <span>慢</span>
                <input type="range" id="speed" min="0.5" max="2.0" step="0.1" value="1.0">
                <span>快</span>
                <span class="speed-value" id="speedDisplay">1.0x</span>
            </div>
        </div>

        <button class="btn-speak" id="speakBtn" onclick="speak()">开始朗读</button>
        <div class="progress-bar" id="progressBar">
            <div class="progress-fill"></div>
        </div>
        <audio id="audioPlayer" controls></audio>
        <div id="status" class="status"></div>

        <div class="mode-hint" id="modeHint">在线引擎使用微软 edge-tts，需要网络连接，音质更好，生成速度快。</div>

        <div class="advanced-link">
            <a href="/advanced">进入进阶页面（GPT-SoVITS 高质量语音）</a>
        </div>
    </div>

    <script>
        let currentMode = 'online';
        const speedSlider = document.getElementById('speed');
        const speedDisplay = document.getElementById('speedDisplay');
        const statusDiv = document.getElementById('status');
        const audioPlayer = document.getElementById('audioPlayer');
        const speakBtn = document.getElementById('speakBtn');
        const progressBar = document.getElementById('progressBar');
        const voiceSelect = document.getElementById('voiceSelect');
        const textArea = document.getElementById('text');
        const charCount = document.getElementById('charCount');
        const modeHint = document.getElementById('modeHint');

        const onlineVoices = """ + str(online_voices) + """;
        const localVoices = """ + str(local_voices_list) + """;

        function setMode(mode) {
            currentMode = mode;
            document.getElementById('modeOnline').classList.toggle('active', mode === 'online');
            document.getElementById('modeLocal').classList.toggle('active', mode === 'local');

            const voices = mode === 'online' ? onlineVoices : localVoices;
            voiceSelect.innerHTML = '';
            voices.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name;
                voiceSelect.appendChild(opt);
            });

            const hints = {
                'online': '在线引擎使用微软 edge-tts，需要网络连接，音质更好，生成速度快。',
                'local': '本地引擎使用 pyttsx3，完全离线，不依赖网络，但音质一般且生成较慢。'
            };
            modeHint.textContent = hints[mode] || '';
        }

        textArea.addEventListener('input', () => {
            charCount.textContent = textArea.value.length;
        });
        charCount.textContent = textArea.value.length;

        speedSlider.addEventListener('input', () => {
            speedDisplay.textContent = parseFloat(speedSlider.value).toFixed(1) + 'x';
        });

        function showStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
        }

        async function pollTaskStatus(taskId) {
            const maxAttempts = 240;
            let attempts = 0;
            while (attempts < maxAttempts) {
                await new Promise(r => setTimeout(r, 1000));
                attempts++;
                const response = await fetch('/api/status/' + taskId);
                const result = await response.json();
                if (result.status === 'completed') return result;
                if (result.status === 'failed') throw new Error(result.error);
            }
            throw new Error('生成超时，请稍后重试');
        }

        async function speak() {
            const text = textArea.value.trim();
            if (!text) {
                showStatus('请输入要朗读的文本', 'error');
                return;
            }

            speakBtn.disabled = true;
            audioPlayer.style.display = 'none';
            progressBar.classList.add('active');
            showStatus('正在生成语音...', 'loading');

            try {
                const submitResponse = await fetch('/api/speak', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        speed: parseFloat(speedSlider.value),
                        voice: voiceSelect.value,
                        mode: currentMode
                    })
                });

                const submitResult = await submitResponse.json();
                if (!submitResult.success) throw new Error(submitResult.error);

                showStatus('正在合成语音，请稍候...', 'loading');
                const result = await pollTaskStatus(submitResult.task_id);

                audioPlayer.src = result.audio_url;
                audioPlayer.style.display = 'block';
                audioPlayer.play();
                showStatus('朗读完成！', 'success');
            } catch (error) {
                // 检测到 API 未运行的错误时，自动打开服务面板
                if (error.message.includes('API 服务未运行') || error.message.includes('无法连接')) {
                    servicePanel.classList.add('show');
                }
                showStatus('失败: ' + error.message, 'error');
            } finally {
                speakBtn.disabled = false;
                progressBar.classList.remove('active');
            }
        }

        setMode('online');
    </script>
</body>
</html>
"""

ADVANCED_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPT-SoVITS 语音合成</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 700px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            position: relative;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #999;
            font-size: 13px;
            margin-bottom: 25px;
        }
        .hw-panel {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        .hw-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }
        .hw-icon { font-size: 16px; }
        .hw-label { color: #999; }
        .hw-value { color: #333; font-weight: 600; }
        .hw-divider { width: 1px; height: 20px; background: #ddd; }
        .engine-toggle {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .engine-toggle label {
            margin: 0;
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }
        .engine-options {
            display: flex;
            gap: 8px;
            flex: 1;
        }
        .engine-btn {
            flex: 1;
            padding: 8px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: white;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            color: #666;
            text-align: center;
        }
        .engine-btn.active {
            border-color: #667eea;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .engine-btn:hover:not(.active) {
            border-color: #667eea;
            color: #667eea;
        }
        .engine-btn .desc {
            font-size: 10px;
            font-weight: normal;
            opacity: 0.8;
            margin-top: 2px;
        }
        .service-toggle {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 100;
        }
        .service-toggle-btn {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            transition: transform 0.2s;
        }
        .service-toggle-btn:hover { transform: scale(1.1); }
        .service-panel {
            position: fixed;
            bottom: 80px;
            right: 20px;
            background: white;
            border-radius: 16px;
            padding: 20px;
            width: 320px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            display: none;
            z-index: 99;
        }
        .service-panel.show { display: block; }
        .service-panel h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .service-panel h3 button {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #999;
        }
        .service-row {
            display: flex;
            align-items: center;
            padding: 10px 12px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 8px;
            border: 1px solid #e0e0e0;
        }
        .service-row:last-child { margin-bottom: 0; }
        .service-info { flex: 1; }
        .service-name { font-weight: 600; color: #333; font-size: 13px; }
        .service-url { font-size: 11px; color: #999; margin-top: 2px; }
        .service-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-right: 8px;
        }
        .status-running { background: #e8f5e9; color: #2e7d32; }
        .status-stopped { background: #ffebee; color: #c62828; }
        .btn-service {
            padding: 5px 12px;
            border: none;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-start { background: #4caf50; color: white; }
        .btn-start:hover { background: #43a047; }
        .btn-start:disabled { background: #999; cursor: not-allowed; }
        .btn-open { background: #2196f3; color: white; }
        .btn-open:hover { background: #1e88e5; }
        .btn-open:disabled { background: #ccc; cursor: not-allowed; }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        select, textarea {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            background: white;
            transition: border-color 0.3s;
        }
        select:focus, textarea:focus { outline: none; border-color: #667eea; }
        textarea { height: 120px; resize: vertical; font-size: 16px; }
        .slider-container { display: flex; align-items: center; gap: 15px; }
        input[type="range"] {
            flex: 1;
            height: 6px;
            -webkit-appearance: none;
            background: #e0e0e0;
            border-radius: 3px;
            outline: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px; height: 20px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }
        .speed-value { min-width: 50px; text-align: center; font-weight: bold; color: #667eea; }
        .btn-speak {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-speak:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-speak:disabled { opacity: 0.6; cursor: not-allowed; }
        .status {
            text-align: center;
            margin-top: 20px;
            padding: 10px;
            border-radius: 8px;
            display: none;
        }
        .status.success { background: #e8f5e9; color: #2e7d32; display: block; }
        .status.error { background: #ffebee; color: #c62828; display: block; }
        .status.loading { background: #e3f2fd; color: #1565c0; display: block; }
        audio { width: 100%; margin-top: 20px; display: none; }
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #e0e0e0;
            border-radius: 2px;
            margin-top: 10px;
            overflow: hidden;
            display: none;
        }
        .progress-bar.active { display: block; }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            animation: progress-animate 1.5s ease-in-out infinite;
        }
        @keyframes progress-animate { 0% { width: 0%; } 50% { width: 70%; } 100% { width: 100%; } }
        .char-count { text-align: right; font-size: 12px; color: #999; margin-top: 5px; }
        .mode-hint { font-size: 12px; color: #999; margin-top: 5px; padding: 8px; background: #f5f5f5; border-radius: 6px; }
        .back-link { text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; }
        .back-link a { color: #667eea; text-decoration: none; font-weight: 500; font-size: 14px; }
        .back-link a:hover { text-decoration: underline; }
        .lang-options {
            display: flex;
            gap: 8px;
        }
        .lang-btn {
            flex: 1;
            padding: 10px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            background: white;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            color: #666;
        }
        .lang-btn.active {
            border-color: #667eea;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .lang-btn:hover:not(.active) {
            border-color: #667eea;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>GPT-SoVITS 语音合成</h1>
        <p class="subtitle">本地模型直接推理 · 高质量情感语音</p>

        <div class="hw-panel">
            <div class="hw-item">
                <span class="hw-icon" id="hwDeviceIcon">""" + str(HARDWARE_INFO.get("device_icon", "🔵")) + """</span>
                <span class="hw-label">设备:</span>
                <span class="hw-value" id="hwDevice">""" + str(HARDWARE_INFO.get("device", "未知")) + """</span>
            </div>
            <div class="hw-divider"></div>
            <div class="hw-item">
                <span class="hw-icon"></span>
                <span class="hw-label">框架:</span>
                <span class="hw-value" id="hwFramework">""" + str(HARDWARE_INFO.get("framework", torch.__version__)) + """</span>
            </div>
            <div class="hw-divider"></div>
            <div class="hw-item">
                <span class="hw-icon">💾</span>
                <span class="hw-label">内存:</span>
                <span class="hw-value">""" + str(HARDWARE_INFO.get("vram", "未知")) + """</span>
            </div>
            <div class="hw-divider"></div>
            <div class="hw-item">
                <span class="hw-icon"></span>
                <span class="hw-label">引擎:</span>
                <span class="hw-value">gsv-tts-lite</span>
            </div>
        </div>

        <div class="engine-toggle">
            <label>推理引擎:</label>
            <div class="engine-options">
                <button class="engine-btn active" id="engineLocal" onclick="setEngine('local')">
                    本地推理
                    <div class="desc">gsv-tts-lite · GPU/CPU · 推荐</div>
                </button>
                <button class="engine-btn" id="engineApi" onclick="setEngine('api')">
                    API 推理
                    <div class="desc">GPT-SoVITS API · 需启动服务</div>
                </button>
            </div>
        </div>

        <div class="form-group">
            <label>GPT 模型选择</label>
            <select id="gptSelect"></select>
        </div>

        <div class="form-group">
            <label>SoVITS 模型选择</label>
            <select id="sovitsSelect"></select>
        </div>

        <div class="form-group">
            <label>语言选择</label>
            <div class="lang-options">
                <button class="lang-btn active" data-lang="ja" onclick="setLang('ja')">日本語</button>
                <button class="lang-btn" data-lang="zh" onclick="setLang('zh')">中文</button>
                <button class="lang-btn" data-lang="en" onclick="setLang('en')">English</button>
            </div>
        </div>

        <div class="form-group">
            <label for="text">输入文本</label>
            <textarea id="text" placeholder="请输入要朗读的文本...">こんにちは、テストです。</textarea>
            <div class="char-count">已输入 <span id="charCount">0</span> 字符</div>
        </div>

        <div class="form-group">
            <label>语速调节</label>
            <div class="slider-container">
                <span>慢</span>
                <input type="range" id="speed" min="0.5" max="2.0" step="0.1" value="1.0">
                <span>快</span>
                <span class="speed-value" id="speedDisplay">1.0x</span>
            </div>
        </div>

        <button class="btn-speak" id="speakBtn" onclick="speak()">开始朗读</button>
        <div class="progress-bar" id="progressBar">
            <div class="progress-fill"></div>
        </div>
        <audio id="audioPlayer" controls></audio>
        <div id="status" class="status"></div>

        <div class="mode-hint" id="modeHint">使用本地 gsv-tts-lite 引擎直接推理，无需启动任何外部服务。</div>

        <div class="back-link">
            <a href="/">返回基础页面</a>
        </div>
    </div>

    <div class="service-toggle">
        <button class="service-toggle-btn" onclick="toggleServicePanel()" title="服务管理">⚙</button>
    </div>

    <div class="service-panel" id="servicePanel">
        <h3>
            服务管理
            <button onclick="toggleServicePanel()">✕</button>
        </h3>
        <div class="service-row">
            <div class="service-info">
                <div class="service-name">GPT-SoVITS API</div>
                <div class="service-url">http://127.0.0.1:""" + str(GPT_SOVITS_API_PORT) + """</div>
            </div>
            <span class="service-status" id="apiStatus">检测中...</span>
            <button class="btn-service btn-open" id="btnOpenApi" onclick="openApi()" disabled>打开</button>
            <button class="btn-service btn-start" id="btnStartApi" onclick="startApi()">启动</button>
        </div>
        <div class="service-row">
            <div class="service-info">
                <div class="service-name">GPT-SoVITS WebUI</div>
                <div class="service-url">http://127.0.0.1:""" + str(GPT_SOVITS_WEBUI_PORT) + """</div>
            </div>
            <span class="service-status" id="webuiStatus">检测中...</span>
            <button class="btn-service btn-open" id="btnOpenWebui" onclick="openWebui()" disabled>打开</button>
            <button class="btn-service btn-start" id="btnStartWebui" onclick="startWebui()">启动</button>
        </div>
    </div>

    <script>
        const gptVoiceList = """ + str(gpt_voice_list) + """;
        const sovitsVoiceList = """ + str(sovits_voice_list) + """;
        const apiPort = """ + str(GPT_SOVITS_API_PORT) + """;
        const webuiPort = """ + str(GPT_SOVITS_WEBUI_PORT) + """;
        const defaultEngine = """ + ('"local"' if GSV_LITE_AVAILABLE else '"api"') + """;
        const speedSlider = document.getElementById('speed');
        const speedDisplay = document.getElementById('speedDisplay');
        const statusDiv = document.getElementById('status');
        const audioPlayer = document.getElementById('audioPlayer');
        const speakBtn = document.getElementById('speakBtn');
        const progressBar = document.getElementById('progressBar');
        const gptSelect = document.getElementById('gptSelect');
        const sovitsSelect = document.getElementById('sovitsSelect');
        const textArea = document.getElementById('text');
        const charCount = document.getElementById('charCount');
        const modeHint = document.getElementById('modeHint');
        const servicePanel = document.getElementById('servicePanel');

        // 当前推理引擎模式
        let currentEngine = defaultEngine;
        let currentLang = 'ja';

        function setLang(lang) {
            currentLang = lang;
            document.querySelectorAll('.lang-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
        }

        function setEngine(engine) {
            currentEngine = engine;
            document.getElementById('engineLocal').classList.toggle('active', engine === 'local');
            document.getElementById('engineApi').classList.toggle('active', engine === 'api');
            const hints = {
                'local': '使用本地 gsv-tts-lite 引擎直接推理，无需启动任何外部服务。',
                'api': '使用 GPT-SoVITS API 推理，需要先启动 API 服务。'
            };
            modeHint.textContent = hints[engine];
        }

        function toggleServicePanel() {
            servicePanel.classList.toggle('show');
        }

        // 初始化 GPT 和 SoVITS 下拉框
        gptSelect.innerHTML = '<option value="">-- 请选择 GPT 模型 --</option>';
        gptVoiceList.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = v.name + (v.version ? ' [' + v.version + ']' : '');
            gptSelect.appendChild(opt);
        });

        sovitsSelect.innerHTML = '<option value="">-- 请选择 SoVITS 模型 --</option>';
        sovitsVoiceList.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = v.name + (v.version ? ' [' + v.version + ']' : '');
            sovitsSelect.appendChild(opt);
        });

        textArea.addEventListener('input', () => {
            charCount.textContent = textArea.value.length;
        });
        charCount.textContent = textArea.value.length;

        speedSlider.addEventListener('input', () => {
            speedDisplay.textContent = parseFloat(speedSlider.value).toFixed(1) + 'x';
        });

        // 服务状态检测
        async function checkService(port) {
            try {
                const r = await fetch('/api/check_port?port=' + port);
                const result = await r.json();
                return result.running;
            } catch (e) {
                return false;
            }
        }

        function updateServiceUI(port, type) {
            const statusEl = document.getElementById(type + 'Status');
            const startBtn = document.getElementById('btnStart' + (type === 'api' ? 'Api' : 'Webui'));
            const openBtn = document.getElementById('btnOpen' + (type === 'api' ? 'Api' : 'Webui'));

            checkService(port).then(running => {
                if (running) {
                    statusEl.textContent = '运行中';
                    statusEl.className = 'service-status status-running';
                    startBtn.textContent = '已启动';
                    startBtn.disabled = true;
                    startBtn.className = 'btn-service btn-start';
                    startBtn.style.background = '#999';
                    openBtn.disabled = false;
                } else {
                    statusEl.textContent = '未启动';
                    statusEl.className = 'service-status status-stopped';
                    startBtn.textContent = '启动';
                    startBtn.disabled = false;
                    startBtn.className = 'btn-service btn-start';
                    startBtn.style.background = '';
                    openBtn.disabled = true;
                }
            });
        }

        async function startService(port, type) {
            const startBtn = document.getElementById('btnStart' + (type === 'api' ? 'Api' : 'Webui'));
            startBtn.disabled = true;
            startBtn.textContent = '启动中...';

            try {
                const r = await fetch('/api/start_service', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ port: port, type: type })
                });
                const result = await r.json();
                if (result.success) {
                    showStatus('服务已启动，请等待几秒后刷新状态', 'success');
                    setTimeout(() => updateServiceUI(port, type), 5000);
                } else {
                    showStatus('启动失败: ' + result.error, 'error');
                    startBtn.disabled = false;
                    startBtn.textContent = '启动';
                }
            } catch (e) {
                showStatus('请求失败: ' + e.message, 'error');
                startBtn.disabled = false;
                startBtn.textContent = '启动';
            }
        }

        function startApi() { startService(apiPort, 'api'); }
        function startWebui() { startService(webuiPort, 'webui'); }
        function openApi() { window.open('http://127.0.0.1:' + apiPort, '_blank'); }
        function openWebui() { window.open('http://127.0.0.1:' + webuiPort, '_blank'); }

        setInterval(() => {
            updateServiceUI(apiPort, 'api');
            updateServiceUI(webuiPort, 'webui');
        }, 10000);

        updateServiceUI(apiPort, 'api');
        updateServiceUI(webuiPort, 'webui');

        function showStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
        }

        async function pollTaskStatus(taskId) {
            const maxAttempts = 600;
            let attempts = 0;
            while (attempts < maxAttempts) {
                await new Promise(r => setTimeout(r, 1000));
                attempts++;
                const response = await fetch('/api/status/' + taskId);
                const result = await response.json();
                if (result.status === 'completed') return result;
                if (result.status === 'failed') throw new Error(result.error);
            }
            throw new Error('生成超时，请稍后重试');
        }

        async function speak() {
            const text = textArea.value.trim();
            if (!text) {
                showStatus('请输入要朗读的文本', 'error');
                return;
            }

            const gptVal = gptSelect.value;
            const sovitsVal = sovitsSelect.value;
            if (!gptVal || !sovitsVal) {
                showStatus('请选择 GPT 和 SoVITS 模型', 'error');
                return;
            }

            // 检查文本长度，长文本可能失败
            if (text.length > 100) {
                const confirmed = confirm(
                    `文本长度 ${text.length} 字符，长文本（> 100 字符）可能导致超时或显存不足。\n\n` +
                    `建议：\n` +
                    `- 使用更短的文本（< 100 字符）\n` +
                    `- 使用 WebUI 处理长文本\n` +
                    `- 将文本分成多段处理\n\n` +
                    `确定继续吗？`
                );
                if (!confirmed) {
                    speakBtn.disabled = false;
                    progressBar.classList.remove('active');
                    return;
                }
            }

            // API 模式下检查服务状态，如果未运行则提示
            if (currentEngine === 'api') {
                const apiRunning = await checkService(apiPort);
                if (!apiRunning) {
                    showStatus('API 服务未运行，请打开右下角服务面板启动 API 服务', 'error');
                    speakBtn.disabled = false;
                    progressBar.classList.remove('active');
                    return;
                }
            }

            speakBtn.disabled = true;
            audioPlayer.style.display = 'none';
            progressBar.classList.add('active');
            showStatus('正在生成语音...', 'loading');

            try {
                const submitResponse = await fetch('/api/speak', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        speed: parseFloat(speedSlider.value),
                        gpt: gptVal,
                        sovits: sovitsVal,
                        lang: currentLang,
                        mode: 'gpt_sovits',
                        engine: currentEngine
                    })
                });

                const submitResult = await submitResponse.json();
                if (!submitResult.success) throw new Error(submitResult.error);

                showStatus('正在合成语音，请稍候...', 'loading');
                const result = await pollTaskStatus(submitResult.task_id);

                audioPlayer.src = result.audio_url;
                audioPlayer.style.display = 'block';
                audioPlayer.play();
                showStatus('朗读完成！', 'success');
            } catch (error) {
                // 检测到 API 未运行的错误时，自动打开服务面板
                if (error.message.includes('API 服务未运行') || error.message.includes('无法连接')) {
                    servicePanel.classList.add('show');
                }
                showStatus('失败: ' + error.message, 'error');
            } finally {
                speakBtn.disabled = false;
                progressBar.classList.remove('active');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/advanced')
def advanced():
    if not GPT_SOVITS_AVAILABLE:
        return render_template_string("""
            <html><body style="font-family:sans-serif;text-align:center;padding:50px;">
                <h1>GPT-SoVITS 模块未启用</h1>
                <p>请确保 advanced_tts.py 文件存在并正确配置。</p>
                <a href="/">返回</a>
            </body></html>
        """)
    return render_template_string(ADVANCED_HTML_TEMPLATE)

@app.route('/api/check_port')
def api_check_port():
    port = request.args.get('port', type=int)
    if not port:
        return jsonify({'running': False})
    return jsonify({'running': _check_port(port)})

@app.route('/api/service_status')
def api_service_status():
    """获取所有服务状态和 GPU 信息"""
    api_running = _check_port(GPT_SOVITS_API_PORT)
    webui_running = _check_port(GPT_SOVITS_WEBUI_PORT)
    
    # 重新检测 GPU 状态
    hw = _get_hw_info()
    
    return jsonify({
        'api': {
            'port': GPT_SOVITS_API_PORT,
            'running': api_running,
            'name': 'GPT-SoVITS API'
        },
        'webui': {
            'port': GPT_SOVITS_WEBUI_PORT,
            'running': webui_running,
            'name': 'GPT-SoVITS WebUI'
        },
        'gpu': hw
    })

@app.route('/api/start_service', methods=['POST'])
def api_start_service():
    global _api_process, _webui_process
    data = request.json
    port = data.get('port')
    service_type = data.get('type')

    if not port or not service_type:
        return jsonify({'success': False, 'error': '参数不完整'})

    if not os.path.exists(GPT_SOVITS_PATH):
        return jsonify({'success': False, 'error': f'GPT-SoVITS 路径不存在：{GPT_SOVITS_PATH}'})

    if _check_port(port):
        return jsonify({'success': True, 'message': '服务已在运行'})

    if service_type == 'api':
        cmd = [
            os.path.join(GPT_SOVITS_PATH, "runtime", "python.exe"),
            "api.py",
            "-a", "127.0.0.1",
            "-p", str(port)
        ]
        success, error = _start_process(cmd, cwd=GPT_SOVITS_PATH)
        if success:
            # 等待几秒让服务启动
            import time
            time.sleep(2)
            if check_api_service():
                return jsonify({'success': True, 'message': 'API 服务已启动'})
            else:
                return jsonify({'success': False, 'error': 'API 服务启动失败，请查看日志'})
        return jsonify({'success': False, 'error': error})

    elif service_type == 'webui':
        cmd = [
            os.path.join(GPT_SOVITS_PATH, "runtime", "python.exe"),
            "webui.py"
        ]
        success, error = _start_process(cmd, cwd=GPT_SOVITS_PATH)
        if success:
            return jsonify({'success': True, 'message': 'WebUI 服务已启动'})
        return jsonify({'success': False, 'error': error})

    return jsonify({'success': False, 'error': '未知服务类型'})

@app.route('/api/speak', methods=['POST'])
def api_speak():
    data = request.json
    text = data.get('text', '')
    speed = data.get('speed', 1.0)
    mode = data.get('mode', 'online')
    engine = data.get('engine', 'local')

    if not text:
        return jsonify({'success': False, 'error': '文本不能为空'})

    if mode == 'gpt_sovits':
        if not GPT_SOVITS_AVAILABLE:
            return jsonify({'success': False, 'error': 'GPT-SoVITS 模块未安装'})
        gpt_key = data.get('gpt', '')
        sovits_key = data.get('sovits', '')
        lang = data.get('lang', 'ja')
        if not gpt_key or not sovits_key:
            return jsonify({'success': False, 'error': '请选择 GPT 和 SoVITS 模型'})
        
        # 如果用户选择本地引擎但本地不可用，自动切换到 API
        if engine == 'local' and not GSV_LITE_AVAILABLE:
            engine = 'api'
        
        # API 模式下检查服务是否运行
        if engine == 'api' and check_api_service:
            if not check_api_service():
                return jsonify({
                    'success': False,
                    'error': f'API 服务未运行，请先启动 GPT-SoVITS API (端口 {GPT_SOVITS_API_PORT})'
                })
        
        result = submit_gpt_sovits_task(text, speed, gpt_key, sovits_key, lang)
    else:
        voice = data.get('voice', 'zh-CN-XiaoxiaoNeural')
        result = submit_task(text, speed, voice, mode)

    return jsonify(result)

@app.route('/api/status/<task_id>')
def api_status(task_id):
    return jsonify(get_task_status(task_id))

@app.route('/audio/<filename>')
def serve_audio(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        ext = os.path.splitext(filename)[1].lower()
        mimetype = 'audio/mp3' if ext == '.mp3' else 'audio/wav'
        return send_file(filepath, mimetype=mimetype)
    return jsonify({'error': '文件不存在'}), 404

if __name__ == "__main__":
    print("\n[INFO] 正在启动 Web 服务...")
    print(f"[INFO] GPT-SoVITS 模块: {'已启用' if GPT_SOVITS_AVAILABLE else '未启用 (需要 advanced_tts.py)'}")
    print(f"[INFO] GPT-SoVITS 路径: {GPT_SOVITS_PATH}")
    print("[INFO] 基础页面: http://localhost:5000")
    print("[INFO] 进阶页面: http://localhost:5000/advanced\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
