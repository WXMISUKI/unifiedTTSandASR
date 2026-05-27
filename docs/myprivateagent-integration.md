# MyPrivateAgent 对接文档

## 推荐接入方式

MyPrivateAgent 应把本服务注册为 `http` transport capability provider。v1 对接入口固定优先使用 `/api/capabilities/*`，不要在 MyPrivateAgent 主进程里直接加载 Edge-TTS、Vosk 模型或语音 provider。

推荐能力登记：

```yaml
capability_id: voice.tts.edge
kind: tts
transport: http
provider: edge_tts
base_url: http://127.0.0.1:8010
health_path: /api/capabilities/voice.tts.edge/health
invoke_path: /api/capabilities/voice.tts.edge/invoke
```

```yaml
capability_id: voice.asr.vosk
kind: asr
transport: http
provider: vosk_server
base_url: http://127.0.0.1:8010
health_path: /api/capabilities/voice.asr.vosk/health
invoke_path: /api/capabilities/voice.asr.vosk/invoke
stream_path: /api/voice/asr/ws
```

## 启动与健康检查

对接前需要先启动两个进程。

```powershell
conda activate TTSASR
python scripts\download_vosk_model.py --model-name vosk-model-small-cn-0.22 --output-dir models
python scripts\start_vosk_server.py --model-path models\vosk-model-small-cn-0.22 --host 127.0.0.1 --port 2700
```

```powershell
conda activate TTSASR
python -m uvicorn app.main:app --reload --port 8010
```

MyPrivateAgent 接入前置检查：

```http
GET http://127.0.0.1:8010/health
GET http://127.0.0.1:8010/api/capabilities/voice.tts.edge/health
GET http://127.0.0.1:8010/api/capabilities/voice.asr.vosk/health
```

`/health` 需要返回 `status=ok`。TTS 和 ASR 的 capability health 都应返回 `status=ready`；如果 ASR 返回 `unavailable`，通常表示 `VOSK_SERVER_URL` 指向的 Vosk WebSocket 服务没有启动或端口不可达。

前端人工验收页面：

```text
http://127.0.0.1:8010/ui
```

## 能力发现

```http
GET http://127.0.0.1:8010/api/capabilities
```

返回示例：

```json
{
  "contract_version": "capability-runtime-v1",
  "capabilities": [
    {
      "capability_id": "voice.tts.edge",
      "kind": "tts",
      "transport": "http",
      "provider": "edge_tts",
      "status": "ready",
      "endpoint": "/api/voice/tts"
    },
    {
      "capability_id": "voice.asr.vosk",
      "kind": "asr",
      "transport": "http",
      "provider": "vosk_server",
      "status": "ready",
      "endpoint": "/api/voice/asr"
    }
  ]
}
```

## TTS 调用

MyPrivateAgent 推荐使用 capability JSON 方式调用 TTS，返回值中读取 `result.audio_base64`。

```http
POST http://127.0.0.1:8010/api/capabilities/voice.tts.edge/invoke
Content-Type: application/json
```

```json
{
  "text": "您好，请问有什么可以帮您？",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+0%",
  "volume": "+0%",
  "pitch": "+0Hz"
}
```

成功返回：

```json
{
  "ok": true,
  "capability_id": "voice.tts.edge",
  "provider": "edge_tts",
  "result": {
    "media_type": "audio/mpeg",
    "audio_base64": "..."
  }
}
```

浏览器测试页和直接播放场景可以使用 `/api/voice/tts`，该接口直接返回二进制 `audio/mpeg`，不作为 MyPrivateAgent 的默认接入方式。

## ASR 调用

v1 不内置音频转码。MyPrivateAgent 或调用方需要把音频预处理成 `16kHz / mono / PCM s16le`。短音频同步调用和实时 WebSocket 二进制 chunk 都遵循同一格式。

短音频同步调用：

```http
POST http://127.0.0.1:8010/api/capabilities/voice.asr.vosk/invoke
Content-Type: application/json
```

```json
{
  "audio_base64": "...",
  "media_type": "audio/pcm;rate=16000;channels=1;format=s16le",
  "language": "zh-cn"
}
```

成功返回：

```json
{
  "ok": true,
  "capability_id": "voice.asr.vosk",
  "provider": "vosk_server",
  "result": {
    "ok": true,
    "provider": "vosk_server",
    "language": "zh-cn",
    "text": "识别结果",
    "partial": false
  }
}
```

实时音频流：

```text
WS ws://127.0.0.1:8010/api/voice/asr/ws
```

客户端发送 `16kHz / mono / PCM s16le` 二进制 chunk。结束一次识别时发送文本帧：

```text
__end__
```

服务端每条消息结构：

```json
{
  "ok": true,
  "provider": "vosk_server",
  "language": "zh-cn",
  "text": "实时识别文本",
  "partial": true,
  "raw": {
    "partial": "实时识别文本"
  }
}
```

`partial=true` 只用于实时预览或临时字幕。最终文本以 `partial=false` 或 `raw.text` 为准。

## 错误响应

`invoke` 调用失败时按非 2xx 处理，并读取 `error.code` 和 `error.message`。

```json
{
  "ok": false,
  "capability_id": "voice.asr.vosk",
  "provider": "vosk_server",
  "error": {
    "code": "VOICE_PROVIDER_UNAVAILABLE",
    "message": "Vosk websocket server is unreachable at 127.0.0.1:2700",
    "provider": "vosk_server"
  }
}
```

MyPrivateAgent 建议将以下错误码映射为可降级的能力不可用状态：

- `VOICE_RUNTIME_DISABLED`：当前服务未启用语音运行时，检查 `ENABLE_VOICE_RUNTIME=true`。
- `VOICE_PROVIDER_UNAVAILABLE`：provider 未配置、依赖缺失或 Vosk 端口不可达。
- `VOICE_PROVIDER_ERROR`：provider 调用时发生运行异常。

## MyPrivateAgent 后续改造建议

1. 在 `capability_runtime` 增加 HTTP provider client。
2. 将 `voice.tts.edge` 和 `voice.asr.vosk` 从 `local` provider 改为 `http` provider。
3. 主项目保留 `/api/capabilities/*` 合同和治理审计。
4. 对 ASR 输入源先做 `16k mono PCM s16le` 标准化；如后续需要直接上传 `wav/mp3/webm/opus`，再单独设计音频转码层。
5. 本项目独立管理语音依赖、Vosk server、Edge-TTS、模型资源和端口。
