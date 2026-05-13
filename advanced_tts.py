"""
GPT-SoVITS TTS 模块
- 主引擎：gsv-tts-lite（本地推理，支持 v1 和 v2 模型格式）
- 备用引擎：GPT-SoVITS WebUI API（当本地引擎失败时自动回退）
"""
import os
import uuid
import threading
import requests
import torch
import soundfile as sf
from my_tts import UPLOAD_FOLDER, tasks

try:
    from gsv_tts.TTS import TTS as GsvTtsEngine
    GSV_LITE_AVAILABLE = True
except ImportError:
    GSV_LITE_AVAILABLE = False

# 导出 API URL 和检测函数供 app.py 使用
GPT_SOVITS_BASE_URL = "http://127.0.0.1"
GPT_SOVITS_API_PORT = 9876

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GPT_SOVITS_BASE_DIR = os.path.join(BASE_DIR, "GPT-Voice")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PRETRAINED_MODELS_DIR = os.path.join(BASE_DIR, "GPT-Voice", ".cache", "gsv")
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
                import pickle
                with open(model_path, "rb") as f:
                    unpickler = pickle.Unpickler(f)
                    while True:
                        try:
                            obj = unpickler.load()
                            if isinstance(obj, dict):
                                if "config" in obj:
                                    config = obj["config"]
                                    if isinstance(config, dict):
                                        data = config.get("data", {})
                                        if isinstance(data, dict):
                                            version = data.get("version", "")
                                            if str(version) in ["2", "v2", "V2"]:
                                                return "v2"
                                            elif version:
                                                return str(version)
                                        break
                                elif "hps" in obj:
                                    hps = obj["hps"]
                                    if hasattr(hps, "data"):
                                        version = getattr(hps.data, "version", "")
                                        if str(version) in ["2", "v2", "V2"]:
                                            return "v2"
                                        elif version:
                                            return str(version)
                                    break
                            break
                        except Exception:
                            break
                    return "v1"
            except Exception:
                return "v1"

        elif model_type == "gpt":
            try:
                import pickle
                with open(model_path, "rb") as f:
                    unpickler = pickle.Unpickler(f)
                    while True:
                        try:
                            obj = unpickler.load()
                            if isinstance(obj, dict):
                                if "config" in obj:
                                    config = obj["config"]
                                    if isinstance(config, dict):
                                        data = config.get("data", {})
                                        if isinstance(data, dict):
                                            version = data.get("version", "")
                                            if str(version) in ["2", "v2", "V2"]:
                                                return "v2"
                                            elif version:
                                                return str(version)
                                        break
                                elif "hps" in obj:
                                    hps = obj["hps"]
                                    if hasattr(hps, "data"):
                                        version = getattr(hps.data, "version", "")
                                        if str(version) in ["2", "v2", "V2"]:
                                            return "v2"
                                        elif version:
                                            return str(version)
                                    break
                            break
                        except Exception:
                            break
                    return "v1"
            except Exception:
                return "v1"

    except Exception:
        return "unknown"


def _scan_character_dir(char_name, char_path):
    """扫描单个角色目录，兼容两种目录结构"""
    ref_audios = []
    gpt_files = []
    sovits_files = []

    gpt_dir = os.path.join(char_path, "GPT_weights")
    sovits_dir = os.path.join(char_path, "SoVITS_weights")
    ref_dir = os.path.join(char_path, "参考音频")

    if not os.path.exists(gpt_dir) and not os.path.exists(sovits_dir):
        gpt_dir = char_path
        sovits_dir = char_path
        ref_dir = char_path

    if os.path.exists(ref_dir):
        for f in sorted(os.listdir(ref_dir)):
            if f.lower().endswith(('.wav', '.mp3', '.flac')) and not f.endswith('.zip'):
                filepath = os.path.join(ref_dir, f)
                text = _clean_name(f)
                lang = "ja" if any('\u3040' <= c <= '\u30ff' for c in text) else "zh"
                ref_audios.append({
                    "id": f"ref_{len(ref_audios)+1}",
                    "name": f"{char_name} - {_clean_name(f)}",
                    "file": filepath,
                    "text": text,
                    "lang": lang,
                    "character": char_name,
                })

    if os.path.exists(gpt_dir):
        for f in sorted(os.listdir(gpt_dir)):
            if f.endswith('.ckpt'):
                gpt_files.append({"id": _clean_name(f), "name": _clean_name(f), "file": os.path.join(gpt_dir, f), "character": char_name})

    if os.path.exists(sovits_dir):
        for f in sorted(os.listdir(sovits_dir)):
            if f.endswith('.pth'):
                sovits_files.append({"id": _clean_name(f), "name": _clean_name(f), "file": os.path.join(sovits_dir, f), "character": char_name})

    return gpt_files, sovits_files, ref_audios


def _auto_scan_all():
    """扫描 GPT-Voice 下所有角色目录，分离 GPT 和 SoVITS 模型"""
    global REF_AUDIOS, GPT_MODELS, SOVITS_MODELS
    REF_AUDIOS = []
    GPT_MODELS = {}
    SOVITS_MODELS = {}

    if not os.path.exists(GPT_SOVITS_BASE_DIR):
        return

    for char_name in sorted(os.listdir(GPT_SOVITS_BASE_DIR)):
        char_path = os.path.join(GPT_SOVITS_BASE_DIR, char_name)
        if not os.path.isdir(char_path) or char_name.startswith('.'):
            continue

        gpt_files, sovits_files, ref_audios = _scan_character_dir(char_name, char_path)

        for g in gpt_files:
            key = f"{char_name}__{g['id']}"
            version = _detect_model_version(g["file"], "gpt")
            GPT_MODELS[key] = {
                "name": f"{char_name} | {g['name']}",
                "version": version,
                "file": g["file"],
                "character": g["character"],
            }

        for s in sovits_files:
            key = f"{char_name}__{s['id']}"
            version = _detect_model_version(s["file"], "sovits")
            SOVITS_MODELS[key] = {
                "name": f"{char_name} | {s['name']}",
                "version": version,
                "file": s["file"],
                "character": s["character"],
            }

        REF_AUDIOS.extend(ref_audios)


def _apply_preset(gpt_key, sovits_key, lang=None):
    """根据 GPT 和 SoVITS 模型获取对应的参考音频配置"""
    gpt_model = GPT_MODELS.get(gpt_key)
    sovits_model = SOVITS_MODELS.get(sovits_key)
    if not gpt_model or not sovits_model:
        return None

    char_name = gpt_model.get("character", "")

    ref_audio = None
    prompt_text = None
    prompt_lang = lang if lang else "ja"

    # 优先查找同角色的参考音频
    for ref in REF_AUDIOS:
        if ref.get("character") == char_name:
            ref_audio = ref["file"]
            prompt_text = ref["text"]
            if not lang:
                prompt_lang = ref["lang"]
            break

    # 如果该角色没有参考音频，报错（避免用其他角色的音频导致效果差）
    if not ref_audio:
        return None

    if ref_audio:
        return {
            "ref_audio": ref_audio,
            "prompt_text": prompt_text,
            "prompt_lang": prompt_lang,
            "gpt_file": gpt_model["file"],
            "sovits_file": sovits_model["file"],
        }
    return None


def _get_tts_engine():
    global _tts_engine, _engine_mode
    if _tts_engine is None and GSV_LITE_AVAILABLE and _engine_mode == "local":
        with _engine_lock:
            if _tts_engine is None:
                try:
                    os.makedirs(PRETRAINED_MODELS_DIR, exist_ok=True)
                    _tts_engine = GsvTtsEngine(models_dir=PRETRAINED_MODELS_DIR, device=DEVICE)
                    print("[INFO] GSV-TTS-Lite 引擎初始化成功（本地推理模式）")
                except Exception as e:
                    print(f"[WARN] 本地引擎初始化失败: {e}，切换到 API 模式")
                    _engine_mode = "api"
                    _tts_engine = None
    return _tts_engine


def _generate_local(text, speed, gpt_key, sovits_key, filepath, lang=None):
    engine = _get_tts_engine()
    if engine is None or _engine_mode != "local":
        raise RuntimeError("本地引擎不可用")

    # 检查文本长度，给出警告
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


def _generate_api(text, speed, gpt_key, sovits_key, filepath, lang=None):
    preset = _apply_preset(gpt_key, sovits_key, lang)
    if not preset:
        raise ValueError(f"模型配置不完整：{gpt_key} + {sovits_key}")

    try:
        response = requests.post(
            GPT_SOVITS_API_URL,
            json={
                "text": text,
                "text_language": preset["prompt_lang"],
                "refer_wav_path": preset["ref_audio"],
                "prompt_text": preset["prompt_text"],
                "prompt_language": preset["prompt_lang"],
                "speed": speed,
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise RuntimeError(f"API 请求失败：{response.status_code} - {response.text}")

        with open(filepath, "wb") as f:
            f.write(response.content)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"无法连接到 GPT-SoVITS API 服务（{GPT_SOVITS_API_URL}），"
            f"请点击右下角 ⚙ 按钮打开服务面板 → 启动 GPT-SoVITS API 服务"
        )
    except requests.exceptions.ReadTimeout:
        raise RuntimeError(
            "API 请求超时，文本可能过长或服务响应过慢。"
            "建议：将文本分段处理或改用 WebUI 完成合成"
        )


def check_api_service():
    """检查 API 服务是否可用"""
    try:
        response = requests.get(GPT_SOVITS_API_URL, timeout=2)
        return response.status_code in [200, 400, 404, 405]
    except:
        return False


def generate_gpt_sovits_audio(text, speed, gpt_key, sovits_key, filepath, task_id, lang=None):
    try:
        if _engine_mode == "local" and _get_tts_engine() is not None:
            try:
                _generate_local(text, speed, gpt_key, sovits_key, filepath, lang)
                tasks[task_id] = {'status': 'completed', 'filepath': filepath}
                return
            except Exception as e:
                print(f"[WARN] 本地推理失败：{e}，切换到 API 模式")

        # 调用 API 前检查服务是否可用
        if not check_api_service():
            raise RuntimeError(
                f"API 服务未运行，请点击右下角 ⚙ 按钮打开服务面板 → 启动 GPT-SoVITS API 服务（端口 {GPT_SOVITS_API_PORT}）"
            )

        _generate_api(text, speed, gpt_key, sovits_key, filepath, lang)
        tasks[task_id] = {'status': 'completed', 'filepath': filepath}
    except Exception as e:
        tasks[task_id] = {'status': 'failed', 'error': str(e)}


def submit_gpt_sovits_task(text, speed, gpt_key, sovits_key, lang=None):
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.wav"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    tasks[task_id] = {'status': 'processing'}

    thread = threading.Thread(target=generate_gpt_sovits_audio, args=(text, speed, gpt_key, sovits_key, filepath, task_id, lang))
    thread.daemon = True
    thread.start()

    return {'success': True, 'task_id': task_id}


_auto_scan_all()

# 启动时立即初始化本地引擎，优先本地推理
if _engine_mode == "local":
    try:
        os.makedirs(PRETRAINED_MODELS_DIR, exist_ok=True)
        _tts_engine = GsvTtsEngine(models_dir=PRETRAINED_MODELS_DIR, device=DEVICE)
        print("[INFO] GSV-TTS-Lite 引擎初始化成功（本地推理模式）")
    except Exception as e:
        print(f"[WARN] 本地引擎初始化失败：{e}，切换到 API 模式")
        _engine_mode = "api"
        _tts_engine = None


__all__ = [
    'submit_gpt_sovits_task',
    'GPT_MODELS',
    'SOVITS_MODELS',
    'REF_AUDIOS',
    'GSV_LITE_AVAILABLE',
    '_engine_mode',
    'check_api_service',
    'GPT_SOVITS_API_PORT',
]
