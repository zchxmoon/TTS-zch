# TTS 语音合成系统

双引擎语音合成系统，包含基础版和进阶版两个独立项目，覆盖从简单文本转语音到高质量角色语音合成的全部需求。

## 项目概览

```
e:\cherry\python\
├── simple_tts/              # 🔵 基础版 — 在线/本地双模式 TTS
│   ├── app.py               #  Web 服务（端口 5001）
│   └── README.md            #  详细文档
│
├── advanced_gpt_sovits/     # 🟣 进阶版 — GPT-SoVITS 角色语音
│   ├── app.py               #  Web 服务（端口 5002）
│   ├── tts_engine.py        #  gsv-tts-lite 推理引擎
│   └── README.md            #  详细文档
│
├── my_tts.py                # 共享模块（任务管理、音频处理）
├── GPT-Voice/               # 模型目录（进阶版使用）
└── README.md                # 本文件
```

## 快速选择

### 🔵 基础版 — simple\_tts（端口 5001）

即时可用的文本转语音服务，无需 GPU，无需加载模型。

```
┌────────────────────────────────────┐
│    在线模式        │    本地模式     │
│  edge-tts          │  pyttsx3       │
│  微软 Azure 语音   │  系统离线语音   │
│  5 种中文音色      │  2 种系统音色   │
│  需要网络          │  完全离线       │
└────────────────────────────────────┘
```

**适用场景：**

- ✅ 快速将文本转为语音
- ✅ 通用朗读、通知播报
- ✅ 无 GPU 环境
- ✅ 追求简单稳定

### 🟣 进阶版 — advanced\_gpt\_sovits（端口 5002）

高质量角色语音合成，使用 gsv-tts-lite 本地推理引擎，支持 GPU 加速。

```
┌──────────────────────────────────────────┐
│          本地推理 + WebUI 备用             │
│  gsv-tts-lite  ·  GPU/CPU  ·  中日英三语  │
│  自定义 GPT + SoVITS 模型 · 角色音色还原  │
└──────────────────────────────────────────┘
```

**适用场景：**

- ✅ 指定角色音色（动漫、虚拟角色）
- ✅ 高质量情感语音合成
- ✅ GPU 加速批量处理
- ✅ 中文/日语/英语多语需求

## 功能对比

| 功能        | 基础版                        | 进阶版                                 |
| --------- | -------------------------- | ----------------------------------- |
| 端口        | **5001**                   | **5002**                            |
| 启动命令      | `python simple_tts/app.py` | `python advanced_gpt_sovits/app.py` |
| 在线语音      | ✅ edge-tts（5 种）            | ❌                                   |
| 本地离线      | ✅ pyttsx3                  | ❌                                   |
| 本地推理      | ❌                          | ✅ gsv-tts-lite                      |
| GPU 加速    | ❌                          | ✅ 自动检测                              |
| 角色定制      | ❌                          | ✅ GPT + SoVITS 模型                   |
| 语言支持      | 中文                         | 中文 / 日语 / 英语                        |
| WebUI 备用  | ❌                          | ✅ 一键启动                              |
| 即时合成      | ✅ 毫秒级                      | ⚠️ 需加载模型                            |
| 音质        | ⭐⭐⭐⭐                       | ⭐⭐⭐⭐⭐                               |
| GPU 要求    | 不需要                        | NVIDIA GPU 4GB+                     |
| Python 版本 | 3.8+                       | 3.10+                               |

## 快速启动

### 基础版

```bash
cd simple_tts
pip install flask edge-tts pyttsx3
python app.py
# 访问 http://localhost:5001
```

### 进阶版（GPU）

```bash
cd advanced_gpt_sovits
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install flask requests psutil soundfile gsv-tts-lite
python app.py
# 访问 http://localhost:5002
```

### 进阶版（CPU）

```bash
cd advanced_gpt_sovits
pip install torch torchvision torchaudio
pip install flask requests psutil soundfile gsv-tts-lite
python app.py
# 访问 http://localhost:5002
```

## 安装依赖速查

| 依赖           | 基础版 | 进阶版（GPU）   | 进阶版（CPU） |
| ------------ | --- | ---------- | -------- |
| flask        | ✅   | ✅          | ✅        |
| requests     | —   | ✅          | ✅        |
| psutil       | —   | ✅          | ✅        |
| edge-tts     | ✅   | —          | —        |
| pyttsx3      | ✅   | —          | —        |
| torch        | —   | ✅（cuda124） | ✅（cpu）   |
| gsv-tts-lite | —   | ✅          | ✅        |
| soundfile    | —   | ✅          | ✅        |

## 系统要求

### 基础版

| 组件     | 最低要求   |
| ------ | ------ |
| Python | 3.8+   |
| 内存     | 512MB  |
| 磁盘     | 100MB  |
| 网络     | 在线模式需要 |
| GPU    | 不需要    |

### 进阶版

| 组件     | 最低要求       | 推荐          |
| ------ | ---------- | ----------- |
| Python | 3.10+      | 3.10+       |
| 内存     | 8GB        | 16GB        |
| 磁盘     | 10GB       | 20GB        |
| GPU    | NVIDIA 4GB | NVIDIA 8GB+ |
| CUDA   | 12.4       | 12.4        |
| 网络     | 首次下载模型需要   | —           |

## 项目文件说明

| 文件                                  | 说明                        |
| ----------------------------------- | ------------------------- |
| `simple_tts/app.py`                 | 基础版 Web 服务（Flask，端口 5001） |
| `advanced_gpt_sovits/app.py`        | 进阶版 Web 服务（Flask，端口 5002） |
| `advanced_gpt_sovits/tts_engine.py` | gsv-tts-lite 推理引擎封装       |
| `my_tts.py`                         | 共享模块：任务队列、音频处理、语音列表       |
| `app.py`                            | 旧版整合项目（同时包含基础和进阶页面）       |
| `advanced_tts.py`                   | 旧版进阶模块                    |

## 模型目录说明

```
GPT-Voice/                  # 进阶版模型目录（项目根目录）
├── .cache/gsv/             # gsv-tts-lite 预训练模型缓存
│   ├── chinese-hubert-base/       # 中文 Hubert
│   ├── chinese-roberta-wwm-ext-large/  # 中文 BERT
│   ├── g2p/                 # 文本转音素
│   ├── sv/                  # 说话人验证
│   ├── s1v3.ckpt            # 默认 GPT 模型
│   └── s2Gv2ProPlus.pth     # 默认 SoVITS 模型
├── 角色A/                   # 自定义角色（标准结构）
│   ├── GPT_weights/         # GPT 模型
│   ├── SoVITS_weights/      # SoVITS 模型
│   └── 参考音频/            # 参考音频
└── 角色B/                   # 自定义角色（扁平结构）
    ├── *.ckpt               # GPT 模型
    ├── *.pth                # SoVITS 模型
    └── *.wav                # 参考音频
```

## 常见问题

### Q: 基础版和进阶版可以同时运行吗？

可以。两个项目使用不同端口（5001 和 5002），互不干扰。分别在不同终端启动即可。

### Q: 进阶版如何切换 GPU/CPU？

自动切换。系统启动时检测 CUDA 可用性，有 GPU 自动使用 GPU，否则回退 CPU。无需手动配置。

### Q: 进阶版支持哪些模型版本？

gsv-tts-lite 兼容 v2/v2pro/v2proplus 格式的 SoVITS 模型。v1 格式需要转换。

### Q: 基础版可以在没有网络的环境使用吗？

可以。切换到本地模式（pyttsx3）即可完全离线使用，但音质和语音种类受系统限制。

### Q: 如何添加新的角色模型（进阶版）？

1. 在 `GPT-Voice/` 下创建角色目录
2. 放入 GPT 模型（.ckpt）+ SoVITS 模型（.pth）+ 参考音频（.wav）
3. 重启服务，模型自动扫描加载

### Q:有GPT-SoVITS为什么不直接用

1. 有GPT-SoVITS直接用就好了，性能要好很多
2. app.py为最初测试，然后进行的分离
3. 此项目由ai生成

<br />

MIT License
