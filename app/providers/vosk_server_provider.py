"""Vosk websocket server provider adapter."""

from __future__ import annotations

import json

from app.config import VoiceServiceSettings
from app.contracts import VoiceTranscriptResult


class VoskServerProvider:
    def __init__(self, settings: VoiceServiceSettings):
        self.settings = settings

    async def transcribe(self, audio: bytes, *, language: str | None = None) -> VoiceTranscriptResult:
        import websockets

        text = ""
        async with websockets.connect(self.settings.vosk_server_url) as ws:
            await ws.send(json.dumps({"config": {"sample_rate": self.settings.vosk_sample_rate}}))
            await ws.send(audio)
            await ws.send(json.dumps({"eof": 1}))
            while True:
                parsed = self._parse_message(await ws.recv())
                text = str(parsed.get("text") or parsed.get("partial") or text or "").strip()
                if "text" in parsed:
                    break
        return VoiceTranscriptResult(
            text=text,
            provider="vosk_server",
            language=language or self.settings.vosk_language,
        )

    @staticmethod
    def _parse_message(raw_message: object) -> dict:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(str(raw_message))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

