# Specification: unifiedTTSandASR

## Purpose
Provide a standalone ASR/TTS service that can be registered as an external capability provider by MyPrivateAgent.

## Requirements
### Voice Runtime Contract
- The service must expose `GET /api/voice/capabilities`.
- It must report provider readiness without requiring runtime execution.
- It must start when providers are disabled or dependencies are unavailable.

### TTS
- `POST /api/voice/tts` accepts `text`, `voice`, `rate`, `volume`, and `pitch`.
- When enabled and Edge-TTS is installed, it returns audio bytes.
- When disabled or unavailable, it returns a structured error.

### ASR
- `POST /api/voice/asr` accepts an uploaded audio file.
- `WS /api/voice/asr/ws` accepts binary PCM chunks and proxies them to a configured Vosk websocket server.
- When disabled or unavailable, endpoints return structured errors.

### Unified Capability Contract
- The service must expose `GET /api/capabilities`.
- It must register `voice.tts.edge` and `voice.asr.vosk`.
- It must expose health and short synchronous invocation endpoints for each registered capability.

## Non-goals
- Do not bundle Vosk model files.
- Do not own long-running job persistence.
- Do not include OCR, multimodal, or video generation in this project.

