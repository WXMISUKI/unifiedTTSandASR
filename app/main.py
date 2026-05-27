"""FastAPI entrypoint for the unified TTS and ASR service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.voice_service import get_voice_service


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class TtsRequest(BaseModel):
    text: str
    voice: str | None = None
    rate: str | None = None
    volume: str | None = None
    pitch: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="unifiedTTSandASR",
        description="Standalone ASR/TTS capability service for MyPrivateAgent and other control planes.",
        version="0.1.0",
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/ui", include_in_schema=False)
    def ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "unifiedTTSandASR"}

    @app.get("/api/voice/capabilities")
    def voice_capabilities() -> dict[str, Any]:
        return get_voice_service().get_voice_capabilities()

    @app.post("/api/voice/tts")
    async def tts(request: TtsRequest):
        result = await get_voice_service().synthesize(request.model_dump(exclude_none=True))
        if not result.ok:
            return JSONResponse(status_code=503, content={"error": result.error.to_payload() if result.error else {}})
        return Response(
            content=result.content or b"",
            media_type=result.media_type,
            headers={"X-Voice-Provider": result.provider},
        )

    @app.post("/api/voice/asr")
    async def asr(file: UploadFile = File(...), language: str | None = None):
        content = await file.read()
        result = await get_voice_service().transcribe(
            content,
            media_type=file.content_type or "application/octet-stream",
            language=language,
        )
        payload = result.to_payload()
        if not payload.get("ok"):
            return JSONResponse(status_code=503, content={"error": payload.get("error") or {}})
        return payload

    @app.websocket("/api/voice/asr/ws")
    async def asr_ws(websocket: WebSocket):
        await websocket.accept()
        service = get_voice_service()
        capabilities = service.get_voice_capabilities()
        asr_capability = capabilities.get("asr") or {}
        if not capabilities.get("enabled") or asr_capability.get("status") != "ready":
            await websocket.send_json(
                {
                    "ok": False,
                    "error": {
                        "code": "VOICE_PROVIDER_UNAVAILABLE" if capabilities.get("enabled") else "VOICE_RUNTIME_DISABLED",
                        "message": asr_capability.get("reason") or "Voice ASR streaming is unavailable.",
                        "provider": asr_capability.get("provider") or "vosk_server",
                    },
                }
            )
            await websocket.close(code=1000)
            return

        import websockets

        try:
            async with websockets.connect(asr_capability.get("server_url")) as vosk_ws:
                sample_rate = int(asr_capability.get("sample_rate") or 16000)
                await vosk_ws.send(json.dumps({"config": {"sample_rate": sample_rate}}))
                while True:
                    client_message = await websocket.receive()
                    if _is_websocket_disconnect_message(client_message):
                        return
                    audio_bytes = client_message.get("bytes")
                    if audio_bytes is not None:
                        await vosk_ws.send(audio_bytes)
                    elif client_message.get("text") == "__end__":
                        await vosk_ws.send(json.dumps({"eof": 1}))
                    else:
                        continue
                    raw_result = await vosk_ws.recv()
                    parsed = json.loads(raw_result) if isinstance(raw_result, str) else {}
                    await websocket.send_json(
                        {
                            "ok": True,
                            "provider": asr_capability.get("provider") or "vosk_server",
                            "language": asr_capability.get("language") or "zh-cn",
                            "text": parsed.get("text") or parsed.get("partial") or "",
                            "partial": "partial" in parsed and "text" not in parsed,
                            "raw": parsed,
                        }
                    )
        except WebSocketDisconnect:
            return
        except RuntimeError as exc:
            if _is_websocket_disconnect_runtime_error(exc):
                return
            await _send_asr_ws_error(websocket, asr_capability, exc)
        except Exception as exc:
            await _send_asr_ws_error(websocket, asr_capability, exc)

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return get_voice_service().list_capabilities()

    @app.get("/api/capabilities/{capability_id}")
    def capability(capability_id: str):
        try:
            return get_voice_service().get_capability(capability_id)
        except LookupError:
            return _not_found(capability_id)

    @app.get("/api/capabilities/{capability_id}/health")
    def capability_health(capability_id: str):
        try:
            return get_voice_service().get_capability_health(capability_id)
        except LookupError:
            return _not_found(capability_id)

    @app.post("/api/capabilities/{capability_id}/invoke")
    async def capability_invoke(capability_id: str, payload: dict[str, Any]):
        try:
            result = await get_voice_service().invoke_capability(capability_id, payload)
        except LookupError:
            return _not_found(capability_id)
        if result.get("ok"):
            return result
        return JSONResponse(status_code=503, content=result)

    return app


def _not_found(capability_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "CAPABILITY_NOT_FOUND",
                "message": f"Capability not found: {capability_id}",
                "capability_id": capability_id,
            }
        },
    )


def _is_websocket_disconnect_message(message: dict[str, Any]) -> bool:
    return message.get("type") == "websocket.disconnect"


def _is_websocket_disconnect_runtime_error(exc: RuntimeError) -> bool:
    return "disconnect message has been received" in str(exc)


async def _send_asr_ws_error(websocket: WebSocket, asr_capability: dict[str, Any], exc: Exception) -> None:
    try:
        await websocket.send_json(
            {
                "ok": False,
                "error": {
                    "code": "VOICE_PROVIDER_ERROR",
                    "message": f"Vosk streaming failed: {exc}",
                    "provider": asr_capability.get("provider") or "vosk_server",
                },
            }
        )
        await websocket.close(code=1011)
    except RuntimeError:
        return


app = create_app()
