# MyPrivateAgent 对接文档

## 推荐接入方式
MyPrivateAgent 后续应把本服务注册为 `http` transport capability provider，而不是继续在主进程中执行语音 provider。

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
      "status": "ready"
    }
  ]
}
```

## TTS 调用
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

## ASR 调用
短音频同步调用：

```http
POST http://127.0.0.1:8010/api/capabilities/voice.asr.vosk/invoke
Content-Type: application/json
```

```json
{
  "audio_base64": "...",
  "media_type": "audio/pcm",
  "language": "zh-cn"
}
```

实时音频流：

```text
WS ws://127.0.0.1:8010/api/voice/asr/ws
```

客户端发送二进制 PCM chunk；结束一次识别时发送文本帧：

```text
__end__
```

## MyPrivateAgent 后续改造建议
1. 在 `capability_runtime` 增加 `http_client.py`。
2. 将 `voice.tts.edge` 和 `voice.asr.vosk` 从 `local` provider 改为 `http` provider。
3. 主项目保留 `/api/capabilities/*` 合同和治理审计。
4. 本项目独立管理语音依赖、Vosk server、Edge-TTS、模型资源和端口。

