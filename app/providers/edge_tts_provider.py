"""Edge-TTS provider adapter."""

from __future__ import annotations

from typing import Any

from app.config import VoiceServiceSettings
from app.contracts import VoiceAudioResult, VoiceRuntimeError


class EdgeTtsProvider:
    def __init__(self, settings: VoiceServiceSettings):
        self.settings = settings

    async def synthesize(self, payload: dict[str, Any]) -> VoiceAudioResult:
        text = str(payload.get("text") or "").strip()
        if not text:
            return VoiceAudioResult(
                content=None,
                media_type="application/json",
                provider="edge_tts",
                error=VoiceRuntimeError(
                    code="VOICE_PROVIDER_ERROR",
                    message="TTS text is required.",
                    provider="edge_tts",
                ),
            )

        import edge_tts

        media_chunks: list[bytes] = []
        communicate = edge_tts.Communicate(
            text=text,
            voice=str(payload.get("voice") or self.settings.edge_tts_default_voice).strip(),
            rate=str(payload.get("rate") or self.settings.edge_tts_rate).strip(),
            volume=str(payload.get("volume") or self.settings.edge_tts_volume).strip(),
            pitch=str(payload.get("pitch") or self.settings.edge_tts_pitch).strip(),
        )
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                media_chunks.append(chunk.get("data") or b"")

        return VoiceAudioResult(
            content=b"".join(media_chunks),
            media_type="audio/mpeg",
            provider="edge_tts",
        )

