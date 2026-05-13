"""基础 TTS 语音合成 Web 服务 - 端口 5001"""
from flask import Flask, render_template_string, request, jsonify, send_file
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from my_tts import submit_task, get_task_status, UPLOAD_FOLDER, online_voices, local_voices_list

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基础 TTS</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:-apple-system,B link Mac System Font,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
        .container{background:#fff;border-radius:20px;padding:40px;box-shadow:0 20px 60px rgba(0,0,0,0.3);width:100%;max-width:800px}
        h1{color:#333;margin-bottom:10px;font-size:2em}
        .subtitle{color:#666;margin-bottom:30px;font-size:0.9em}
        .mode-selector{display:flex;gap:10px;margin-bottom:20px}
        .mode-btn{flex:1;padding:15px;border:2px solid #e0e0e0;background:#fff;border-radius:10px;cursor:pointer;font-size:1em;transition:all 0.3s}
        .mode-btn.active{border-color:#667eea;background:#667eea;color:#fff}
        textarea{width:100%;min-height:150px;padding:15px;border:2px solid #e0e0e0;border-radius:10px;resize:vertical;font-size:1em;margin-bottom:15px}
        select{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px;font-size:1em;margin-bottom:15px}
        button{width:100%;padding:15px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;border:none;border-radius:10px;font-size:1.1em;cursor:pointer;transition:transform 0.2s}
        button:hover{transform:translateY(-2px)}
        button:disabled{opacity:0.5;cursor:not-allowed}
        .status{margin-top:20px;padding:15px;border-radius:10px;text-align:center}
        .status.success{background:#4CAF50;color:#fff}
        .status.error{background:#f44336;color:#fff}
        .progress-bar{width:100%;height:4px;background:#e0e0e0;border-radius:2px;margin-top:15px;overflow:hidden}
        .progress-bar.active::after{content:'';display:block;width:0;height:100%;background:#4CAF50;transition:width 0.3s}
        .progress-bar.active::after{animation:progress 2s infinite}
        @keyframes progress{0%{width:0%}50%{width:100%}100%{width:0%}}
        audio{width:100%;margin-top:20px}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ 基础 TTS</h1>
        <p class="subtitle">在线/本地双模式语音合成</p>
        <div class="mode-selector">
            <button class="mode-btn active" onclick="setMode('online')">在线模式</button>
            <button class="mode-btn" onclick="setMode('local')">本地模式</button>
        </div>
        <textarea id="text" placeholder="请输入要合成的文本..."></textarea>
        <select id="voiceSelect"><option value="" disabled selected>请选择语音</option></select>
        <button id="generateBtn" onclick="generate()">🎵 生成语音</button>
        <div class="progress-bar" id="progressBar"></div>
        <div class="status" id="status" style="display:none"></div>
        <audio id="audioPlayer" controls style="display:none"></audio>
    </div>
    <script>
        let currentMode='online';
        const voices={online:{{ online_voices|tojson }},local:{{ local_voices|tojson }}};
        function initVoices(){updateVoiceList(currentMode)}
        function setMode(mode){
            currentMode=mode;
            document.querySelectorAll('.mode-btn').forEach(btn=>{
                btn.classList.toggle('active',btn.textContent.includes(mode==='online'?'在线':'本地'));
            });
            updateVoiceList(mode);
        }
        function updateVoiceList(mode){
            const select=document.getElementById('voiceSelect');
            select.innerHTML='<option value="" disabled selected>请选择语音</option>';
            voices[mode].forEach(voice=>{
                const option=document.createElement('option');
                option.value=voice.id;
                option.textContent=voice.name;
                select.appendChild(option);
            });
        }
        async function generate(){
            const text=document.getElementById('text').value.trim();
            const voice=document.getElementById('voiceSelect').value;
            if(!text){showStatus('请输入文本','error');return}
            if(!voice){showStatus('请选择语音','error');return}
            const btn=document.getElementById('generateBtn');
            const progressBar=document.getElementById('progressBar');
            const audioPlayer=document.getElementById('audioPlayer');
            btn.disabled=true;audioPlayer.style.display='none';progressBar.classList.add('active');
            try{
                const response=await fetch('/api/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,speed:1.0,voice,mode:currentMode})});
                const result=await response.json();
                if(!result.success)throw new Error(result.error);
                const audioData=await pollStatus(result.task_id);
                audioPlayer.src=audioData.audio_url;
                audioPlayer.style.display='block';audioPlayer.play();
                showStatus('生成成功！','success');
            }catch(error){showStatus('失败：'+error.message,'error')}
            finally{btn.disabled=false;progressBar.classList.remove('active')}
        }
        async function pollStatus(taskId){
            for(let i=0;i<300;i++){
                await new Promise(r=>setTimeout(r,1000));
                const response=await fetch('/api/status/'+taskId);
                const result=await response.json();
                if(result.status==='completed')return result;
                if(result.status==='failed')throw new Error(result.error);
            }
            throw new Error('超时');
        }
        function showStatus(message,type){
            const status=document.getElementById('status');
            status.textContent=message;
            status.className='status '+type;
            status.style.display='block';
            setTimeout(()=>status.style.display='none',3000);
        }
        initVoices();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, online_voices=online_voices, local_voices=local_voices_list)

@app.route('/api/speak', methods=['POST'])
def api_speak():
    data = request.json
    text = data.get('text', '')
    speed = data.get('speed', 1.0)
    voice = data.get('voice', '')
    mode = data.get('mode', 'online')
    if not text:
        return jsonify({'success': False, 'error': '文本不能为空'})
    if not voice:
        return jsonify({'success': False, 'error': '请选择语音'})
    result = submit_task(text, speed, voice, mode)
    return jsonify(result)

@app.route('/api/status/<task_id>')
def api_status(task_id):
    result = get_task_status(task_id)
    if result.get('status') == 'completed':
        result['audio_url'] = f'/audio/{os.path.basename(result["filepath"])}'
    return jsonify(result)

@app.route('/audio/<filename>')
def serve_audio(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='audio/wav')
    return jsonify({'error': '文件不存在'}), 404

if __name__ == '__main__':
    print('=' * 60)
    print('🎙️ 基础 TTS 语音合成服务')
    print('=' * 60)
    print(f'在线语音数：{len(online_voices)}')
    print(f'本地语音数：{len(local_voices_list)}')
    print(f'服务地址：http://localhost:5001')
    print('=' * 60)
    app.run(host='0.0.0.0', port=5001, debug=False)