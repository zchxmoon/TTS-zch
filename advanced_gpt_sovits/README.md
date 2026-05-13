# GPT-SoVITS 进阶 TTS

高质量角色语音合成服务，使用 gsv-tts-lite 本地推理引擎，支持中文 / 日语 / 英语三种语言。

## 功能特性

- **本地推理** — gsv-tts-lite 引擎，支持 GPU/CUDA 加速和 CPU 模式
- **三语合成** — 中文、日语、英语，自动加载对应 BERT 模型
- **角色音色** — 自定义 GPT + SoVITS 模型组合，还原角色声线
- **WebUI 备用** — 本地引擎不可用时，一键启动 WebUI 完成合成
- **自动跳转** — 启动 WebUI 后自动打开浏览器
- **GPU 实时检测** — 启动时自动识别 GPU/CPU，页面显示硬件信息

## 系统要求

| 组件 | GPU 版（推荐） | CPU 版 |
|------|---------------|--------|
| **Python** | 3.10+ | 3.10+ |
| **PyTorch** | 2.x + CUDA | 2.x (cpu) |
| **NVIDIA GPU** | GTX/RTX 系列，显存 4GB+ | 不需要 |
| **CUDA** | 12.4 | 不需要 |
| **显存** | 4GB+（推荐 8GB） | 系统内存 8GB+ |

## 安装指南

### 1. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# Windows 激活
venv\Scripts\activate

# Linux/Mac 激活
source venv/bin/activate
```

### 2. 安装 PyTorch

根据你的硬件选择以下两种方式之一：

#### GPU 版（CUDA 12.4，推荐）

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

> 如果使用其他 CUDA 版本，请访问 [pytorch.org](https://pytorch.org/get-started/locally/) 获取对应安装命令。

#### CPU 版

```bash
pip install torch torchvision torchaudio
```

PyTorch CPU 版默认不包含 CUDA 支持，推理将在 CPU 上进行。

### 3. 验证 GPU 可用性（GPU 版）

```python
import torch
print(f"CUDA 可用：{torch.cuda.is_available()}")          # 应为 True
print(f"GPU 设备：{torch.cuda.get_device_name(0)}")
print(f"CUDA 版本：{torch.version.cuda}")
```

如果输出 `CUDA 可用：False`，说明 PyTorch 未正确安装 CUDA 版，请重新执行 GPU 版安装命令。

### 4. 安装其他依赖

```bash
pip install flask requests psutil soundfile gsv-tts-lite
```

### 5. 安装 CUDA 工具包（GPU 版，可选）

如果 `torch.cuda.is_available()` 返回 `False`，可能需要安装 NVIDIA 驱动和 CUDA 工具包：

1. **安装 NVIDIA 驱动**：[NVIDIA Driver Download](https://www.nvidia.com/download/index.aspx)
2. **安装 CUDA 12.4**：[CUDA Toolkit 12.4](https://developer.nvidia.com/cuda-12-4-0-download-archive)

安装完成后重启，再次运行步骤 3 验证。

### 6. 配置模型目录

确保以下目录结构存在：

```
GPT-Voice/
├── .cache/gsv/                   # gsv-tts-lite 预训练模型缓存
│   ├── chinese-hubert-base/      # 中文 Hubert
│   ├── chinese-roberta-wwm-ext-large/  # 中文 BERT（GPU 推理必需）
│   ├── g2p/                      # 文本转音素
│   ├── sv/                       # 说话人验证
│   ├── s1v3.ckpt                 # 默认 GPT 模型
│   └── s2Gv2ProPlus.pth          # 默认 SoVITS 模型
├── 角色名/                       # 自定义角色目录
│   ├── GPT_weights/              # GPT 模型文件（.ckpt）
│   ├── SoVITS_weights/           # SoVITS 模型文件（.pth）
│   └── 参考音频/                 # 参考音频文件（.wav/.mp3）
└── 角色名/                       # 扁平结构也支持
    ├── 角色名-e10.ckpt           # GPT 模型
    ├── 角色名_e10_s820.pth       # SoVITS 模型
    └── 参考音频.wav              # 参考音频
```

> **注意**：模型目录需放在 `../GPT-Voice/` 下（即项目根目录），或通过环境变量 `GPT_SOVITS_PATH` 指定路径。

## 启动服务

```bash
cd advanced_gpt_sovits
python app.py
```

启动后显示：

```
============================================================
🎙️ GPT-SoVITS 进阶 TTS 服务
============================================================
GPT 模型数：3
SoVITS 模型数：4
参考音频数：4
本地引擎可用：是
硬件信息：GPU - NVIDIA GeForce RTX 4060 Laptop GPU
三语支持：中文 / 日语 / 英语
服务地址：http://localhost:5002
============================================================
```

### GPU 模式启动

系统自动检测 GPU，无需额外配置。启动日志中 `硬件信息` 显示 GPU 型号即表示 GPU 模式已启用。

### CPU 模式启动

如果未安装 CUDA 或没有 NVIDIA GPU，PyTorch 会自动回退到 CPU 模式。启动日志中 `硬件信息` 显示 CPU 即表示 CPU 模式。

> CPU 模式推理速度较慢（约 5-20 秒/句），建议使用短文本（< 50 字符）。

## 使用方法

### 1. 访问页面

打开浏览器访问：**http://localhost:5002**

### 2. 选择模型

- 选择对应的 **GPT 模型** 和 **SoVITS 模型**
- 同一角色的 GPT 和 SoVITS 模型需配对使用

### 3. 选择语言

根据输入文本的语言选择对应的语言按钮：
- 🇯🇵 日本語 — 输入日语文本
- 🇨🇳 中文 — 输入中文文本
- 🇺🇸 English — 输入英文文本

### 4. 输入文本并生成

- 建议文本长度 **< 100 字符**
- 长文本（> 100 字符）会弹出确认提示
- 过长文本或长时音频可能导致 GPU 显存不足

### 5. 语速调节

拖动滑块调节语速（0.5x ~ 2.0x），默认为 1.0x。

### 6. 服务管理（可选）

点击右下角 ⚙ 按钮打开服务面板：
- 启动 WebUI（当本地引擎不可用时作为备用）
- 查看 WebUI 服务状态
- 启动成功后自动打开浏览器

## API 接口

### 提交合成任务

```bash
curl -X POST http://localhost:5002/api/speak \
  -H "Content-Type: application/json" \
  -d '{
    "text": "こんにちは",
    "speed": 1.0,
    "gpt": "Yukino__Yukino_Strong-e25",
    "sovits": "Yukino__Yukino_Strong",
    "lang": "ja"
  }'
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 要合成的文本 |
| `speed` | float | 否 | 语速（0.5~2.0，默认 1.0） |
| `gpt` | string | 是 | GPT 模型 key |
| `sovits` | string | 是 | SoVITS 模型 key |
| `lang` | string | 否 | 语言（ja/zh/en，默认 ja） |

返回示例：

```json
{"success": true, "task_id": "xxx-xxx-xxx"}
```

### 查询任务状态

```bash
curl http://localhost:5002/api/status/xxx-xxx-xxx
```

返回示例：

```json
{"status": "completed", "filepath": "temp_audio/xxx.wav", "audio_url": "/audio/xxx.wav"}
```

### 获取音频文件

```bash
curl http://localhost:5002/audio/xxx.wav --output output.wav
```

### 启动 WebUI

```bash
curl -X POST http://localhost:5002/api/start_service \
  -H "Content-Type: application/json" \
  -d '{"port": 9874}'
```

### 检查端口

```bash
curl http://localhost:5002/api/check_port?port=9874
```

## 模型管理

### 添加新角色

1. 在 `GPT-Voice/` 下创建角色目录
2. 放入 GPT 模型文件（`.ckpt`）
3. 放入 SoVITS 模型文件（`.pth`）
4. 放入参考音频文件（`.wav` / `.mp3` / `.flac`）

支持两种目录结构：

**标准结构：**
```
角色名/GPT_weights/*.ckpt
角色名/SoVITS_weights/*.pth
角色名/参考音频/*.wav
```

**扁平结构：**
```
角色名/*.ckpt    → GPT 模型
角色名/*.pth     → SoVITS 模型
角色名/*.wav     → 参考音频
```

### 模型版本

gsv-tts-lite 主要支持 **v2/v2pro** 格式的 SoVITS 模型。v1 格式模型建议转换为 v2 格式后使用。

## 多语言支持说明

### 中文合成

- 需要 `chinese-roberta-wwm-ext-large` 模型（包含 `pytorch_model.bin`）
- 首次合成中文文本时自动加载 BERT 模型（约 2-3 秒）
- BERT 模型位置：`GPT-Voice/.cache/gsv/chinese-roberta-wwm-ext-large/`

### 日语合成

- 无需额外模型，使用默认管线
- 日语模型为 Yukino 等角色训练时已包含日语特征

### 英语合成

- 无需额外模型，使用 g2p 音素转换
- 英语音素数据位于 `GPT-Voice/.cache/gsv/g2p/en/`

### 如何丢失中文模型后重下

```python
from gsv_tts.Download import download_model
download_model("chinese-roberta.zip", r"GPT-Voice/.cache/gsv")
```

## 性能优化

### GPU 模式（默认）

| 指标 | 表现 |
|------|------|
| 推理速度 | 0.5~2 秒/句 |
| 显存占用 | 2~4 GB |
| 推荐文本 | < 100 字符 |
| 适用场景 | 批量处理、实时合成 |

### CPU 模式

| 指标 | 表现 |
|------|------|
| 推理速度 | 5~20 秒/句 |
| 内存占用 | 4~8 GB |
| 推荐文本 | < 50 字符 |
| 适用场景 | 无 GPU 环境、简单测试 |

### 性能建议

- 使用短文本（< 50 字符）可获得最佳效果
- GPU 模式使用 `torch.bfloat16` 精度，自动优化显存
- 如需推理长文本，建议使用 WebUI 或将文本分段处理
- 关闭其他 GPU 程序可释放显存

## 故障排除

### 本地引擎不可用

```
错误：本地推理引擎不可用，请使用 WebUI 进行语音合成
```

**原因：** gsv-tts-lite 未安装或初始化失败
**解决：**
1. 确认已安装：`pip install gsv-tts-lite`
2. 点击页面右下角 ⚙ 按钮启动 WebUI 作为备用
3. 确认预训练模型文件完整

### GPU 检测失败

```
硬件信息：CPU - ...
```

**原因：** PyTorch 未安装 CUDA 版，或 NVIDIA 驱动缺失
**解决：**
1. 确认 NVIDIA 驱动已安装：在终端运行 `nvidia-smi`
2. 重新安装 GPU 版 PyTorch：`pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124`
3. 验证 CUDA：`python -c "import torch; print(torch.cuda.is_available())"`

### 显存不足

```
错误：GPU 显存不足
```

**解决：**
1. 使用更短的文本（< 50 字符）
2. 关闭其他 GPU 程序（如游戏、其他 AI 应用）
3. 重启服务释放显存
4. 切换到 CPU 模式（卸载 CUDA 版 PyTorch，安装 CPU 版）

### 中文合成失败

```
错误：Error no file named pytorch_model.bin
```

**原因：** 中文 BERT 模型不完整
**解决：** 重新下载模型：
```python
from gsv_tts.Download import download_model
download_model("chinese-roberta.zip", r"GPT-Voice/.cache/gsv")
```

### SoVITS 模型版本不兼容

```
错误：The Sovits model is not the v2/v2pro/v2proplus version
```

**原因：** 模型为 v1 格式，gsv-tts-lite 不支持
**解决：** 使用 v2 格式的模型，或将 v1 模型转换为 v2 格式

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                  Web 浏览器 (5002)                    │
├─────────────────────────────────────────────────────┤
│                   Flask Web 服务                      │
├─────────────────────────────────────────────────────┤
│              tts_engine.py (推理引擎)                 │
├───────────────────┬─────────────────────────────────┤
│  gsv-tts-lite     │      WebUI (9874, 备用)          │
│  (本地推理)       │                                  │
├───────────────────┴─────────────────────────────────┤
│                 PyTorch (GPU/CPU)                    │
├─────────────────────────────────────────────────────┤
│                 CUDA / NVIDIA 驱动                    │
└─────────────────────────────────────────────────────┘
```

## 项目结构

```
advanced_gpt_sovits/
├── app.py                  # Web 服务（Flask，端口 5002）
├── tts_engine.py           # TTS 核心引擎（gsv-tts-lite）
├── temp_audio/             # 音频文件临时存储
├── README.md               # 本文件
```

```
GPT-Voice/                  # 模型目录（项目根目录）
├── .cache/gsv/             # 预训练模型缓存
├── 角色A/                  # 角色模型
└── 角色B/
```

## 许可证

MIT License
