"""Local Vosk websocket server used by the ASR provider."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import websockets

logger = logging.getLogger("unified_tts_asr.vosk_server")


RecognizerFactory = Callable[[int], Any]


def configure_vosk_server_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for logger_name in ("websockets.server", "websockets.asyncio.server"):
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


class VoskStreamingSession:
    """Stateful recognizer wrapper for one websocket connection."""

    def __init__(self, recognizer_factory: RecognizerFactory, *, sample_rate: int):
        self._recognizer_factory = recognizer_factory
        self._sample_rate = sample_rate
        self._recognizer: Any | None = None

    def accept_text(self, message: str) -> dict[str, Any]:
        payload = self._parse_json(message)
        config = payload.get("config")
        if isinstance(config, dict):
            sample_rate = int(config.get("sample_rate") or self._sample_rate)
            if self._recognizer is None:
                self._sample_rate = sample_rate
            return {"ok": True, "sample_rate": self._sample_rate}
        if payload.get("eof"):
            return self._parse_json(self._recognizer_instance().FinalResult())
        return {"ok": False, "error": {"code": "UNSUPPORTED_MESSAGE", "message": "Unsupported text message."}}

    def accept_audio(self, chunk: bytes) -> dict[str, Any]:
        recognizer = self._recognizer_instance()
        if recognizer.AcceptWaveform(chunk):
            return self._parse_json(recognizer.Result())
        return self._parse_json(recognizer.PartialResult())

    def _recognizer_instance(self) -> Any:
        if self._recognizer is None:
            self._recognizer = self._recognizer_factory(self._sample_rate)
            set_words = getattr(self._recognizer, "SetWords", None)
            if callable(set_words):
                set_words(True)
        return self._recognizer

    @staticmethod
    def _parse_json(raw: object) -> dict[str, Any]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}


def build_recognizer_factory(model_path: Path) -> RecognizerFactory:
    if not model_path.exists():
        raise FileNotFoundError(f"Vosk model path does not exist: {model_path}")
    try:
        from vosk import KaldiRecognizer, Model, SetLogLevel
    except ModuleNotFoundError as exc:
        raise RuntimeError("Python package 'vosk' is required. Run: python -m pip install -r requirements.txt") from exc

    SetLogLevel(-1)
    model = Model(str(model_path))

    def create(sample_rate: int) -> Any:
        return KaldiRecognizer(model, sample_rate)

    return create


async def serve_vosk_websocket(
    *,
    model_path: Path,
    host: str,
    port: int,
    sample_rate: int,
) -> None:
    recognizer_factory = build_recognizer_factory(model_path)

    async def handler(websocket: Any) -> None:
        session = VoskStreamingSession(recognizer_factory, sample_rate=sample_rate)
        async for message in websocket:
            if isinstance(message, bytes):
                response = session.accept_audio(message)
            else:
                response = session.accept_text(str(message))
            await websocket.send(json.dumps(response, ensure_ascii=False))

    logger.info("Starting Vosk websocket server on ws://%s:%s with model %s", host, port, model_path)
    async with websockets.serve(handler, host, port, max_size=None):
        await asyncio.Future()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local Vosk websocket ASR server.")
    parser.add_argument(
        "--model-path",
        default=os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-cn-0.22"),
        help="Path to an extracted Vosk model directory.",
    )
    parser.add_argument("--host", default=os.getenv("VOSK_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VOSK_SERVER_PORT", "2700")))
    parser.add_argument("--sample-rate", type=int, default=int(os.getenv("VOSK_SAMPLE_RATE", "16000")))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    configure_vosk_server_logging()
    args = parse_args(argv)
    asyncio.run(
        serve_vosk_websocket(
            model_path=Path(args.model_path).resolve(),
            host=args.host,
            port=args.port,
            sample_rate=args.sample_rate,
        )
    )


if __name__ == "__main__":
    main()
