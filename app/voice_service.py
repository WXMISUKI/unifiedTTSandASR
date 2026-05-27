"""Voice capability service facade."""

from __future__ import annotations

import base64
from importlib.util import find_spec
from typing import Any

from app.config import VoiceServiceSettings, get_settings
from app.contracts import (
    CAPABILITY_CONTRACT_VERSION,
    VOICE_CONTRACT_VERSION,
    VoiceAudioResult,
    VoiceRuntimeError,
    VoiceTranscriptResult,
)


class VoiceService:
    def __init__(self, settings: VoiceServiceSettings | None = None):
        self.settings = settings or get_settings()

    def get_voice_capabilities(self) -> dict[str, Any]:
        return {
            "contract_version": VOICE_CONTRACT_VERSION,
            "enabled": self.settings.enabled,
            "asr": self._build_asr_capability(),
            "tts": self._build_tts_capability(),
            "endpoints": {
                "capabilities": "/api/voice/capabilities",
                "asr": "/api/voice/asr",
                "asr_stream": "/api/voice/asr/ws",
                "tts": "/api/voice/tts",
            },
        }

    def list_capabilities(self) -> dict[str, Any]:
        return {
            "contract_version": CAPABILITY_CONTRACT_VERSION,
            "capabilities": [
                self._capability_contract(
                    capability_id="voice.tts.edge",
                    kind="tts",
                    transport="http",
                    provider="edge_tts",
                    title="Edge TTS",
                    description="Synthesize text into speech through Edge-TTS.",
                    endpoint="/api/voice/tts",
                    provider_status=self._build_tts_capability(),
                    input_schema={
                        "type": "object",
                        "required": ["text"],
                        "properties": {
                            "text": {"type": "string"},
                            "voice": {"type": "string"},
                            "rate": {"type": "string"},
                            "volume": {"type": "string"},
                            "pitch": {"type": "string"},
                        },
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "media_type": {"type": "string"},
                            "audio_base64": {"type": "string"},
                        },
                    },
                ),
                self._capability_contract(
                    capability_id="voice.asr.vosk",
                    kind="asr",
                    transport="http",
                    provider="vosk_server",
                    title="Vosk ASR",
                    description="Transcribe audio through a configured Vosk websocket server.",
                    endpoint="/api/voice/asr",
                    provider_status=self._build_asr_capability(),
                    input_schema={
                        "type": "object",
                        "required": ["audio_base64"],
                        "properties": {
                            "audio_base64": {"type": "string"},
                            "media_type": {"type": "string"},
                            "language": {"type": "string"},
                        },
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "language": {"type": "string"},
                            "partial": {"type": "boolean"},
                        },
                    },
                ),
            ],
        }

    def get_capability(self, capability_id: str) -> dict[str, Any]:
        for capability in self.list_capabilities()["capabilities"]:
            if capability["capability_id"] == capability_id:
                return capability
        raise LookupError(f"Capability not found: {capability_id}")

    def get_capability_health(self, capability_id: str) -> dict[str, Any]:
        capability = self.get_capability(capability_id)
        return {
            "capability_id": capability["capability_id"],
            "kind": capability["kind"],
            "provider": capability["provider"],
            "transport": capability["transport"],
            "status": capability["status"],
            "reason": capability.get("reason") or "",
        }

    async def invoke_capability(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if capability_id == "voice.tts.edge":
            result = await self.synthesize(payload)
            if not result.ok:
                return self._capability_error(capability_id, "edge_tts", result.error)
            return {
                "ok": True,
                "capability_id": capability_id,
                "provider": result.provider,
                "result": {
                    "media_type": result.media_type,
                    "audio_base64": base64.b64encode(result.content or b"").decode("ascii"),
                },
            }
        if capability_id == "voice.asr.vosk":
            audio_base64 = str(payload.get("audio_base64") or "")
            try:
                audio = base64.b64decode(audio_base64)
            except Exception:
                audio = b""
            result = await self.transcribe(
                audio,
                media_type=str(payload.get("media_type") or "application/octet-stream"),
                language=payload.get("language"),
            )
            if not result.ok:
                return self._capability_error(capability_id, "vosk_server", result.error)
            return {
                "ok": True,
                "capability_id": capability_id,
                "provider": result.provider,
                "result": result.to_payload() | {"ok": True},
            }
        raise LookupError(f"Capability not found: {capability_id}")

    async def synthesize(self, payload: dict[str, Any]) -> VoiceAudioResult:
        disabled_error = self._disabled_error(self.settings.tts_provider)
        if disabled_error:
            return VoiceAudioResult(None, "application/json", self.settings.tts_provider, disabled_error)
        if self.settings.tts_provider != "edge_tts":
            return self._provider_unavailable_audio(
                "VOICE_PROVIDER_UNAVAILABLE",
                f"Unsupported TTS provider: {self.settings.tts_provider}",
            )
        if find_spec("edge_tts") is None:
            return self._provider_unavailable_audio(
                "VOICE_PROVIDER_UNAVAILABLE",
                "edge-tts is not installed. Run pip install -r requirements.txt.",
            )
        try:
            from app.providers.edge_tts_provider import EdgeTtsProvider

            return await EdgeTtsProvider(self.settings).synthesize(payload)
        except Exception as exc:
            return self._provider_unavailable_audio("VOICE_PROVIDER_ERROR", f"Edge-TTS synthesis failed: {exc}")

    async def transcribe(
        self,
        audio: bytes,
        *,
        media_type: str = "application/octet-stream",
        language: str | None = None,
    ) -> VoiceTranscriptResult:
        preliminary = self._validate_asr(audio, language=language)
        if not preliminary.ok:
            return preliminary
        try:
            from app.providers.vosk_server_provider import VoskServerProvider

            return await VoskServerProvider(self.settings).transcribe(audio, language=language)
        except Exception as exc:
            return self._provider_unavailable_transcript(
                "VOICE_PROVIDER_ERROR",
                f"Vosk ASR transcription failed: {exc}",
                language=language,
            )

    def _validate_asr(self, audio: bytes, *, language: str | None) -> VoiceTranscriptResult:
        disabled_error = self._disabled_error(self.settings.asr_provider)
        if disabled_error:
            return VoiceTranscriptResult("", self.settings.asr_provider, language or self.settings.vosk_language, error=disabled_error)
        if self.settings.asr_provider != "vosk_server":
            return self._provider_unavailable_transcript(
                "VOICE_PROVIDER_UNAVAILABLE",
                f"Unsupported ASR provider: {self.settings.asr_provider}",
                language=language,
            )
        if not self.settings.vosk_server_url.strip():
            return self._provider_unavailable_transcript(
                "VOICE_PROVIDER_UNAVAILABLE",
                "VOSK_SERVER_URL is required for vosk_server ASR.",
                language=language,
            )
        if find_spec("websockets") is None:
            return self._provider_unavailable_transcript(
                "VOICE_PROVIDER_UNAVAILABLE",
                "websockets is not installed. Run pip install -r requirements.txt.",
                language=language,
            )
        if not audio:
            return self._provider_unavailable_transcript("VOICE_UNSUPPORTED_MEDIA_TYPE", "Audio payload is empty.", language=language)
        return VoiceTranscriptResult("", self.settings.asr_provider, language or self.settings.vosk_language)

    def _build_asr_capability(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return self._provider_status("disabled", "ENABLE_VOICE_RUNTIME=false", provider=self.settings.asr_provider) | {
                "mode": self.settings.vosk_mode,
                "language": self.settings.vosk_language,
                "realtime_supported": self.settings.asr_provider == "vosk_server",
            }
        if self.settings.asr_provider != "vosk_server":
            return self._provider_status("unsupported", "Only vosk_server is supported in v1.", provider=self.settings.asr_provider) | {
                "mode": "unsupported",
                "language": self.settings.vosk_language,
                "realtime_supported": False,
            }
        if not self.settings.vosk_server_url.strip():
            return self._provider_status("unconfigured", "VOSK_SERVER_URL is required.", provider="vosk_server") | {
                "mode": self.settings.vosk_mode,
                "language": self.settings.vosk_language,
                "realtime_supported": True,
            }
        if find_spec("websockets") is None:
            return self._provider_status("missing_dependency", "Python package 'websockets' is not installed.", provider="vosk_server") | {
                "mode": self.settings.vosk_mode,
                "language": self.settings.vosk_language,
                "realtime_supported": True,
            }
        connection_error = self._probe_websocket_handshake(self.settings.vosk_server_url)
        if connection_error:
            return self._provider_status("unavailable", connection_error, provider="vosk_server") | {
                "mode": self.settings.vosk_mode,
                "language": self.settings.vosk_language,
                "realtime_supported": True,
                "server_url": self.settings.vosk_server_url,
                "sample_rate": self.settings.vosk_sample_rate,
            }
        return {
            "provider": "vosk_server",
            "mode": self.settings.vosk_mode,
            "language": self.settings.vosk_language,
            "status": "ready",
            "reason": "",
            "realtime_supported": True,
            "server_url": self.settings.vosk_server_url,
            "sample_rate": self.settings.vosk_sample_rate,
        }

    def _build_tts_capability(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return self._provider_status("disabled", "ENABLE_VOICE_RUNTIME=false", provider=self.settings.tts_provider) | {
                "default_voice": self.settings.edge_tts_default_voice,
            }
        if self.settings.tts_provider != "edge_tts":
            return self._provider_status("unsupported", "Only edge_tts is supported in v1.", provider=self.settings.tts_provider) | {
                "default_voice": self.settings.edge_tts_default_voice,
            }
        if find_spec("edge_tts") is None:
            return self._provider_status("missing_dependency", "Python package 'edge-tts' is not installed.", provider="edge_tts") | {
                "default_voice": self.settings.edge_tts_default_voice,
            }
        return {
            "provider": "edge_tts",
            "status": "ready",
            "reason": "",
            "default_voice": self.settings.edge_tts_default_voice,
            "rate": self.settings.edge_tts_rate,
            "volume": self.settings.edge_tts_volume,
            "pitch": self.settings.edge_tts_pitch,
        }

    @staticmethod
    def _provider_status(status: str, reason: str, *, provider: str) -> dict[str, Any]:
        return {"provider": provider, "status": status, "reason": reason}

    @staticmethod
    def _probe_websocket_handshake(server_url: str) -> str:
        try:
            from websockets.sync.client import connect

            with connect(server_url, open_timeout=0.5, close_timeout=0.1):
                return ""
        except Exception as exc:
            return f"Vosk websocket server is unreachable at {server_url}: {exc}"

    def _capability_contract(
        self,
        *,
        capability_id: str,
        kind: str,
        transport: str,
        provider: str,
        title: str,
        description: str,
        endpoint: str,
        provider_status: dict[str, Any],
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "capability_id": capability_id,
            "kind": kind,
            "transport": transport,
            "provider": provider,
            "title": title,
            "description": description,
            "status": provider_status.get("status") or "unknown",
            "reason": provider_status.get("reason") or "",
            "endpoint": endpoint,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "metadata": {"service": "unifiedTTSandASR"},
        }

    def _disabled_error(self, provider: str) -> VoiceRuntimeError | None:
        if self.settings.enabled:
            return None
        return VoiceRuntimeError(
            code="VOICE_RUNTIME_DISABLED",
            message="Voice runtime is disabled. Set ENABLE_VOICE_RUNTIME=true to enable it.",
            provider=provider,
        )

    def _provider_unavailable_audio(self, code: str, message: str) -> VoiceAudioResult:
        return VoiceAudioResult(
            content=None,
            media_type="application/json",
            provider=self.settings.tts_provider,
            error=VoiceRuntimeError(code=code, message=message, provider=self.settings.tts_provider),
        )

    def _provider_unavailable_transcript(self, code: str, message: str, *, language: str | None) -> VoiceTranscriptResult:
        return VoiceTranscriptResult(
            text="",
            provider=self.settings.asr_provider,
            language=language or self.settings.vosk_language,
            error=VoiceRuntimeError(code=code, message=message, provider=self.settings.asr_provider),
        )

    @staticmethod
    def _capability_error(capability_id: str, provider: str, error: VoiceRuntimeError | None) -> dict[str, Any]:
        return {
            "ok": False,
            "capability_id": capability_id,
            "provider": provider,
            "error": error.to_payload() if error else {"code": "CAPABILITY_INVOCATION_FAILED", "message": "Invocation failed."},
        }


def get_voice_service() -> VoiceService:
    return VoiceService()
