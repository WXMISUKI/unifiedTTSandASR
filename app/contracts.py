"""Provider-neutral contracts for the standalone voice service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VOICE_CONTRACT_VERSION = "voice-runtime-v1"
CAPABILITY_CONTRACT_VERSION = "capability-runtime-v1"


@dataclass(frozen=True)
class VoiceRuntimeError:
    code: str
    message: str
    provider: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.provider:
            payload["provider"] = self.provider
        return payload


@dataclass(frozen=True)
class VoiceAudioResult:
    content: bytes | None
    media_type: str
    provider: str
    error: VoiceRuntimeError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_payload(self) -> dict[str, Any]:
        if self.ok:
            return {
                "ok": True,
                "provider": self.provider,
                "media_type": self.media_type,
                "byte_length": len(self.content or b""),
            }
        return {"ok": False, "error": self.error.to_payload() if self.error else {}}


@dataclass(frozen=True)
class VoiceTranscriptResult:
    text: str
    provider: str
    language: str
    partial: bool = False
    error: VoiceRuntimeError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_payload(self) -> dict[str, Any]:
        if self.ok:
            return {
                "ok": True,
                "provider": self.provider,
                "language": self.language,
                "text": self.text,
                "partial": self.partial,
            }
        return {"ok": False, "error": self.error.to_payload() if self.error else {}}

