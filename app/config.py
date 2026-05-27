"""Environment-backed service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional local convenience
    load_dotenv = None


if load_dotenv:
    load_dotenv()


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class VoiceServiceSettings:
    enabled: bool = False
    asr_provider: str = "vosk_server"
    tts_provider: str = "edge_tts"
    vosk_mode: str = "server"
    vosk_server_url: str = "ws://127.0.0.1:2700"
    vosk_language: str = "zh-cn"
    vosk_sample_rate: int = 16000
    edge_tts_default_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_volume: str = "+0%"
    edge_tts_pitch: str = "+0Hz"

    @classmethod
    def from_env(cls) -> "VoiceServiceSettings":
        return cls(
            enabled=_env_flag("ENABLE_VOICE_RUNTIME", "false"),
            asr_provider=os.getenv("VOICE_ASR_PROVIDER", "vosk_server").strip() or "vosk_server",
            tts_provider=os.getenv("VOICE_TTS_PROVIDER", "edge_tts").strip() or "edge_tts",
            vosk_mode=os.getenv("VOSK_MODE", "server").strip() or "server",
            vosk_server_url=os.getenv("VOSK_SERVER_URL", "ws://127.0.0.1:2700").strip(),
            vosk_language=os.getenv("VOSK_LANGUAGE", "zh-cn").strip() or "zh-cn",
            vosk_sample_rate=int(os.getenv("VOSK_SAMPLE_RATE", "16000")),
            edge_tts_default_voice=(
                os.getenv("EDGE_TTS_DEFAULT_VOICE", "zh-CN-XiaoxiaoNeural").strip()
                or "zh-CN-XiaoxiaoNeural"
            ),
            edge_tts_rate=os.getenv("EDGE_TTS_RATE", "+0%").strip() or "+0%",
            edge_tts_volume=os.getenv("EDGE_TTS_VOLUME", "+0%").strip() or "+0%",
            edge_tts_pitch=os.getenv("EDGE_TTS_PITCH", "+0Hz").strip() or "+0Hz",
        )


def get_settings() -> VoiceServiceSettings:
    return VoiceServiceSettings.from_env()

