"""
GPT-SoVITS TTS 核心引擎
- 主引擎：gsv-tts-lite（本地推理，支持 v1 和 v2 模型格式）
- 备用方案：启动 WebUI 进行语音合成（当本地引擎不可用时）
"""
import os
import sys
import uuid
import threading
import torch
import soundfile as sf

# 添加父目录到 Python 路径，以便导入 my_tts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from my_tts import UPLOAD_FOLDER, tasks

try:
    from gsv_tts.TTS import TTS as GsvTtsEngine
    GSV_LITE_AVAILABLE = True
except ImportError:
    GSV_LITE_AVAILABLE = False

GPT_SOVITS_BASE_URL = "http://127.0.0.1"
GPT_SOVITS_API_PORT = 9876
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GPT_SOVITS_BASE_DIR = os.path.join(BASE_DIR, "..", "GPT-Voice")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PRETRAINED_MODELS_DIR = os.path.join(BASE_DIR, "..", "GPT-Voice", ".cache", "gsv")
GPT_SOVITS_API_URL = os.environ.get("GPT_SOVITS_API_URL", "http://127.0.0.1:9876")

REF_AUDIOS = []
GPT_MODELS = {}
SOVITS_MODELS = {}
_tts_engine = None
_engine_lock = threading.Lock()
_engine_mode = "local" if GSV_LITE_AVAILABLE else "api"


def _clean_name(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]


def _detect_model_version(model_path, model_type="sovits"):
    """检测模型版本（v1 或 v2）"""
    try:
        if not os.path.exists(model_path):
            return "unknown"
        
        if model_type == "sovits":
            try:
                model = torch.load(model_path, map_location='cpu', weights_only=True)
            except Exception:
                model = torch.load(model_path, map_location='cpu', weights_only=False)
            
            if "model" in model:
                return "v1"
            elif "enc_p" in model or "emb_g" in model:
                return "v2"
            else:
                return "unknown"
        elif model_type == "gpt":
            try:
                model = torch.load(model_path, map_location='cpu')
            except Exception:
                return "unknown"
            
            if isinstance(model, dict) and "model" in model:
                return "v1"
            else:
                return "v2"
    except Exception as e:
        print(f"[WARN] 模型版本检测失败：{model_path} - {e}")
        return "unknown"


def _scan_models():
    """扫描所有角色目录下的 GPT 和 SoVITS 模型，以及参考音频
    支持两种目录结构：
    1. 标准结构：character/GPT_weights/, character/SoVITS_weights/, character/参考音频/
    2. 扁平结构：character/*.ckpt (GPT), character/*.pth (SoVITS), character/*.wav (参考音频)
    """
    global GPT_MODELS, SOVITS_MODELS, REF_AUDIOS
    
    if not os.path.exists(GPT_SOVITS_BASE_DIR):
        print(f"[ERROR] GPT-SoVITS 目录不存在：{GPT_SOVITS_BASE_DIR}")
        return
    
    for character in sorted(os.listdir(GPT_SOVITS_BASE_DIR)):
        if character.startswith('.'):
            continue
        
        char_path = os.path.join(GPT_SOVITS_BASE_DIR, character)
        if not os.path.isdir(char_path):
            continue
        
        gpt_dir = os.path.join(char_path, "GPT_weights")
        sovits_dir = os.path.join(char_path, "SoVITS_weights")
        audio_dir = os.path.join(char_path, "参考音频")
        
        if all(os.path.exists(d) for d in [gpt_dir, sovits_dir, audio_dir]):
            # 标准三级目录结构
            _scan_standard_structure(character, char_path, gpt_dir, sovits_dir, audio_dir)
        else:
            # 扁平结构：模型文件直接在角色目录下
            _scan_flat_structure(character, char_path)
    
    if GPT_MODELS:
        print(f"[INFO] 已加载 {len(GPT_MODELS)} 个 GPT 模型")
        print(f"[INFO] 已加载 {len(SOVITS_MODELS)} 个 SoVITS 模型")
        print(f"[INFO] 已加载 {len(REF_AUDIOS)} 个参考音频")
    else:
        print(f"[WARN] 未找到任何 GPT-SoVITS 模型")


def _scan_standard_structure(character, char_path, gpt_dir, sovits_dir, audio_dir):
    """扫描标准三级目录结构"""
    for gpt_file in os.listdir(gpt_dir):
        if gpt_file.endswith('.ckpt') or gpt_file.endswith('.pth'):
            gpt_path = os.path.join(gpt_dir, gpt_file)
            version = _detect_model_version(gpt_path, "gpt")
            name = _clean_name(gpt_file)
            key = f"{character}__{name}"
            GPT_MODELS[key] = {
                "name": name,
                "character": character,
                "file": gpt_path,
                "version": version
            }
    
    for sovits_file in os.listdir(sovits_dir):
        if sovits_file.endswith('.pth'):
            sovits_path = os.path.join(sovits_dir, sovits_file)
            version = _detect_model_version(sovits_path, "sovits")
            name = _clean_name(sovits_file)
            key = f"{character}__{name}"
            SOVITS_MODELS[key] = {
                "name": name,
                "character": character,
                "file": sovits_path,
                "version": version
            }
    
    for audio_file in os.listdir(audio_dir):
        if audio_file.endswith(('.wav', '.mp3', '.flac')):
            audio_path = os.path.join(audio_dir, audio_file)
            REF_AUDIOS.append({
                "name": _clean_name(audio_file),
                "character": character,
                "path": audio_path
            })


def _scan_flat_structure(character, char_path):
    """扫描扁平目录结构（模型文件直接在角色目录下）"""
    has_gpt = False
    has_sovits = False
    has_audio = False
    
    for file in sorted(os.listdir(char_path)):
        file_path = os.path.join(char_path, file)
        if os.path.isdir(file_path) or file == 'train.log':
            continue
        
        if file.endswith('.ckpt'):
            version = _detect_model_version(file_path, "gpt")
            name = _clean_name(file)
            key = f"{character}__{name}"
            GPT_MODELS[key] = {
                "name": name,
                "character": character,
                "file": file_path,
                "version": version
            }
            has_gpt = True
        
        elif file.endswith('.pth'):
            version = _detect_model_version(file_path, "sovits")
            name = _clean_name(file)
            key = f"{character}__{name}"
            SOVITS_MODELS[key] = {
                "name": name,
                "character": character,
                "file": file_path,
                "version": version
            }
            has_sovits = True
        
        elif file.endswith(('.wav', '.mp3', '.flac')):
            REF_AUDIOS.append({
                "name": _clean_name(file),
                "character": character,
                "path": file_path
            })
            has_audio = True
    
    if has_gpt or has_sovits or has_audio:
        print(f"[INFO] 扫描到扁平结构角色「{character}」：GPT={has_gpt}, SoVITS={has_sovits}, 音频={has_audio}")


_scan_models()


def _match_score(gpt_name, sovits_name):
    """计算 GPT 和 SoVITS 模型的匹配评分"""
    score = 0
    gpt_info = GPT_MODELS.get(gpt_name, {})
    sovits_info = SOVITS_MODELS.get(sovits_name, {})
    
    gpt_type = "Strong" if "Strong" in gpt_name else ("Weak" if "Weak" in gpt_name else None)
    sovits_type = "Strong" if "Strong" in sovits_name else ("Weak" if "Weak" in sovits_name else None)
    
    if gpt_type == sovits_type and gpt_type in ["Strong", "Weak"]:
        score += 100
    
    gpt_ver = gpt_info.get("version", "unknown")
    sovits_ver = sovits_info.get("version", "unknown")
    if gpt_ver == sovits_ver and gpt_ver != "unknown":
        score += 50
    
    if gpt_info.get("character") == sovits_info.get("character"):
        score += 20
    
    if (gpt_type and not sovits_type) or (not gpt_type and sovits_type):
        score += 10
    
    return score


def _get_tts_engine():
    """获取或创建 TTS 引擎实例"""
    global _tts_engine, _engine_mode
    
    if not GSV_LITE_AVAILABLE:
        return None
    
    if _tts_engine is None and _engine_mode == "local":
        try:
            print(f"[INFO] 初始化 gsv-tts-lite 引擎（{DEVICE} 模式）...")
            _tts_engine = GsvTtsEngine(
                device=DEVICE,
                models_dir=PRETRAINED_MODELS_DIR
            )
            print(f"[INFO] gsv-tts-lite 引擎初始化成功（{DEVICE} 模式）")
        except Exception as e:
            print(f"[ERROR] gsv-tts-lite 引擎初始化失败：{e}")
            _engine_mode = "api"
            return None
    
    return _tts_engine


def _apply_preset(gpt_key, sovits_key, lang=None):
    """根据 GPT 和 SoVITS 模型选择最优预设"""
    gpt_info = GPT_MODELS.get(gpt_key)
    sovits_info = SOVITS_MODELS.get(sovits_key)
    if not gpt_info or not sovits_info:
        return None
    
    preset = {
        "gpt_file": gpt_info["file"],
        "sovits_file": sovits_info["file"],
        "prompt_text": "",
        "prompt_lang": lang or "ja",
        "ref_audio": None
    }
    
    matching_audios = [a for a in REF_AUDIOS if a["character"] == sovits_info["character"]]
    if matching_audios:
        best_audio = matching_audios[0]
        preset["ref_audio"] = best_audio["path"]
        preset["prompt_text"] = best_audio["name"]
    
    return preset if preset["ref_audio"] else None


def _generate_local(text, speed, gpt_key, sovits_key, filepath, lang=None):
    engine = _get_tts_engine()
    if engine is None or _engine_mode != "local":
        raise RuntimeError("本地引擎不可用")
    
    if len(text) > 100:
        print(f"[WARN] 文本长度 {len(text)} 字符，长文本可能导致显存不足或超时")
    
    preset = _apply_preset(gpt_key, sovits_key, lang)
    if not preset:
        raise ValueError(f"模型配置不完整：{gpt_key} + {sovits_key}")
    
    with _engine_lock:
        try:
            if preset["gpt_file"] not in engine.gpt_models:
                engine.load_gpt_model(preset["gpt_file"])
            if preset["sovits_file"] not in engine.sovits_models:
                engine.load_sovits_model(preset["sovits_file"])
            if preset["ref_audio"] not in engine.prompt_audio_cache:
                engine.cache_prompt_audio(preset["ref_audio"], preset["prompt_text"])
            if preset["ref_audio"] not in engine.spk_audio_cache:
                engine.cache_spk_audio(preset["ref_audio"])
            
            result = engine.infer(
                spk_audio_path=preset["ref_audio"],
                prompt_audio_path=preset["ref_audio"],
                prompt_audio_text=preset["prompt_text"],
                text=text,
                speed=speed,
                gpt_model=preset["gpt_file"],
                sovits_model=preset["sovits_file"],
            )
            
            sf.write(filepath, result.audio_data, result.samplerate)
        except RuntimeError as e:
            error_msg = str(e)
            if "显存" in error_msg.lower() or "out of memory" in error_msg.lower() or "OOM" in error_msg.upper():
                raise RuntimeError("GPU 显存不足，请尝试使用更短的文本或关闭其他程序后重试")
            raise





def generate_gpt_sovits_audio(text, speed, gpt_key, sovits_key, filepath, task_id, lang=None):
    try:
        if _engine_mode == "local" and _get_tts_engine() is not None:
            _generate_local(text, speed, gpt_key, sovits_key, filepath, lang)
            tasks[task_id] = {'status': 'completed', 'filepath': filepath}
        else:
            raise RuntimeError("本地推理引擎不可用，请使用 WebUI 进行语音合成")
    except Exception as e:
        tasks[task_id] = {'status': 'failed', 'error': str(e)}
        raise


def submit_gpt_sovits_task(text, speed, gpt_key, sovits_key, lang=None):
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.wav"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    tasks[task_id] = {'status': 'processing'}
    
    thread = threading.Thread(
        target=generate_gpt_sovits_audio,
        args=(text, speed, gpt_key, sovits_key, filepath, task_id, lang)
    )
    thread.daemon = True
    thread.start()
    
    return {'success': True, 'task_id': task_id}


# 导出给 app.py 使用
__all__ = [
    'submit_gpt_sovits_task',
    'GPT_MODELS',
    'SOVITS_MODELS',
    'REF_AUDIOS',
    'GSV_LITE_AVAILABLE',
    '_engine_mode',
    'GPT_SOVITS_BASE_DIR',
]