# unifiedTTSandASR

`unifiedTTSandASR` 是一个独立的 ASR/TTS 能力服务，用于向 `MyPrivateAgent` 以及其他 Agent Runtime Control Plane 项目提供统一的语音能力接口。

该服务将语音供应商能力从主项目后端中拆分出来，便于独立管理供应商依赖、Python 运行环境、模型文件以及实时音频基础设施，降低主业务服务的部署复杂度和依赖耦合。

## 能力范围

- `voice.tts.edge`：通过 Edge-TTS 提供文本转语音能力。
- `voice.asr.vosk`：通过本项目内置的 Vosk WebSocket 服务提供语音转文本能力。
- `/ui`：浏览器测试页面，可检查服务状态、测试实时 ASR 录音、测试 TTS 音频生成。

## 环境准备

项目推荐使用独立的 Conda 环境运行，避免 ASR/TTS 依赖污染全局 Python 环境。

```powershell
cd D:\AI\AIcode\unifiedTTSandASR
conda create -n TTSASR python=3.11 -y
conda activate TTSASR
python -m pip config list
python -m pip install -r requirements.txt
copy .env.example .env
```

如果 `python -m pip config list` 显示了国内镜像，例如 `https://mirrors.aliyun.com/pypi/simple/`，说明 pip 全局加速已经生效。

## 配置

编辑 `.env`：

```env
ENABLE_VOICE_RUNTIME=true
VOICE_TTS_PROVIDER=edge_tts
VOICE_ASR_PROVIDER=vosk_server
VOSK_SERVER_URL=ws://127.0.0.1:2700
VOSK_MODEL_PATH=models/vosk-model-small-cn-0.22
```

`VOSK_MODEL_PATH` 需要指向已经解压的 Vosk 模型目录。中文轻量测试建议使用 `vosk-model-small-cn-0.22`，模型文件不提交到 Git，默认放在 `models/` 下。

## 下载 Vosk 模型

在项目根目录创建模型目录，并下载、解压中文小模型：

```powershell
conda activate TTSASR
python scripts\download_vosk_model.py --model-name vosk-model-small-cn-0.22 --output-dir models
```

解压完成后的目录应类似：

```text
D:\AI\AIcode\unifiedTTSandASR\models\vosk-model-small-cn-0.22
```

## 启动服务

需要启动两个进程。

第一个终端：启动 Vosk WebSocket ASR 服务。

```powershell
cd D:\AI\AIcode\unifiedTTSandASR
conda activate TTSASR
python scripts\start_vosk_server.py --model-path models\vosk-model-small-cn-0.22 --host 127.0.0.1 --port 2700
```

第二个终端：启动 FastAPI 能力服务。

```powershell
cd D:\AI\AIcode\unifiedTTSandASR
conda activate TTSASR
python -m uvicorn app.main:app --reload --port 8010
```

启动后可访问：

- Swagger：`http://127.0.0.1:8010/docs`
- 前端测试页面：`http://127.0.0.1:8010/ui`
- 健康检查：`http://127.0.0.1:8010/health`

## 前端测试页面

访问 `http://127.0.0.1:8010/ui` 后可以完成三类测试：

- 服务状态：检查 FastAPI 是否可连接、运行时是否启用、ASR/TTS provider 是否 ready。
- ASR 实时录音：点击“开始录音”，浏览器会将麦克风音频转为 `16k PCM s16le` 并通过 `/api/voice/asr/ws` 发送到后端，再由后端转发给 Vosk WebSocket 服务。
- TTS 文本转语音：输入文字后点击“生成并播放”，页面会调用 `/api/voice/tts` 并播放返回的音频。

如果 ASR 显示 `unavailable`，通常表示 `VOSK_SERVER_URL` 配置的地址没有 Vosk 服务监听，请先确认 `2700` 端口已启动。

## API

语音兼容接口：

```http
GET  /api/voice/capabilities
POST /api/voice/tts
POST /api/voice/asr
WS   /api/voice/asr/ws
```

统一能力接口：

```http
GET  /api/capabilities
GET  /api/capabilities/{capability_id}
GET  /api/capabilities/{capability_id}/health
POST /api/capabilities/{capability_id}/invoke
```

与 `MyPrivateAgent` 能力运行时集成时，优先使用 `/api/capabilities/*` 系列接口。

## 测试

```powershell
conda activate TTSASR
python -m unittest discover -s tests -v
```
