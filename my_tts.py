import os
import uuid
import asyncio
import threading
import edge_tts
import pyttsx3

UPLOAD_FOLDER = 'temp_audio'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

tasks = {}

online_voices = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (女声-推荐)"},
    {"id": "zh-CN-YunxiNeural", "name": "云希 (男声)"},
    {"id": "zh-CN-YunjianNeural", "name": "云健 (男声-沉稳)"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊 (女声)"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬 (男声)"},
]

_local_engine = pyttsx3.init()
local_voices_list = []
for v in _local_engine.getProperty('voices'):
    display_name = v.name if v.name else v.id.split('\\')[-1]
    local_voices_list.append({"id": v.id, "name": display_name})

def generate_online_audio(text, speed, voice, filepath, task_id):
    async def _run():
        rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"-{int((1.0 - speed) * 100)}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(filepath)
    try:
        asyncio.run(_run())
        tasks[task_id] = {'status': 'completed', 'filepath': filepath}
    except Exception as e:
        tasks[task_id] = {'status': 'failed', 'error': str(e)}

def generate_local_audio(text, speed, voice_id, filepath, task_id):
    try:
        engine = pyttsx3.init()
        engine.setProperty('voice', voice_id)
        engine.setProperty('rate', int(200 * speed))
        engine.save_to_file(text, filepath)
        engine.runAndWait()
        engine.stop()
        tasks[task_id] = {'status': 'completed', 'filepath': filepath}
    except Exception as e:
        tasks[task_id] = {'status': 'failed', 'error': str(e)}

def submit_task(text, speed, voice, mode):
    task_id = str(uuid.uuid4())
    ext = 'mp3' if mode == 'online' else 'wav'
    filename = f"{task_id}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    tasks[task_id] = {'status': 'processing'}

    if mode == 'online':
        target = generate_online_audio
        args = (text, speed, voice, filepath, task_id)
    elif mode == 'local':
        target = generate_local_audio
        args = (text, speed, voice, filepath, task_id)
    else:
        return {'success': False, 'error': f'Unknown mode: {mode}'}

    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    thread.start()

    return {'success': True, 'task_id': task_id}

def get_task_status(task_id):
    if task_id not in tasks:
        return {'status': 'not_found'}
    task = tasks[task_id]
    if task['status'] == 'completed':
        return {
            'status': 'completed',
            'audio_url': f'/audio/{task["filepath"].split(os.sep)[-1]}'
        }
    elif task['status'] == 'failed':
        return {'status': 'failed', 'error': task['error']}
    return {'status': 'processing'}
