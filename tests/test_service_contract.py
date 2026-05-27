import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import _is_websocket_disconnect_message, _is_websocket_disconnect_runtime_error, create_app
from app.voice_service import VoiceService


class ServiceContractTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            "os.environ",
            {
                "ENABLE_VOICE_RUNTIME": "false",
                "VOICE_ASR_PROVIDER": "vosk_server",
                "VOICE_TTS_PROVIDER": "edge_tts",
                "VOSK_SERVER_URL": "ws://127.0.0.1:2700",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app())

    def tearDown(self):
        self.env_patch.stop()

    def test_health_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_ui_page_is_available(self):
        response = self.client.get("/ui")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("语音能力调试台", response.text)

    def test_voice_capabilities_are_disabled_by_default(self):
        response = self.client.get("/api/voice/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["contract_version"], "voice-runtime-v1")
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["tts"]["status"], "disabled")
        self.assertEqual(payload["asr"]["status"], "disabled")

    def test_asr_capability_reports_unavailable_when_vosk_server_is_down(self):
        service = VoiceService()
        settings = service.settings.__class__(
            enabled=True,
            vosk_server_url="ws://127.0.0.1:1",
        )
        capability = VoiceService(settings).get_voice_capabilities()["asr"]

        self.assertEqual(capability["status"], "unavailable")
        self.assertIn("Vosk websocket server is unreachable", capability["reason"])

    def test_asr_capability_probe_uses_websocket_handshake(self):
        service = VoiceService()

        self.assertTrue(hasattr(service, "_probe_websocket_handshake"))
        self.assertFalse(hasattr(service, "_probe_websocket_tcp"))

    def test_asr_websocket_disconnect_is_treated_as_normal_shutdown(self):
        self.assertTrue(_is_websocket_disconnect_message({"type": "websocket.disconnect"}))
        self.assertFalse(_is_websocket_disconnect_message({"type": "websocket.receive", "text": "__end__"}))
        self.assertTrue(
            _is_websocket_disconnect_runtime_error(
                RuntimeError('Cannot call "receive" once a disconnect message has been received.')
            )
        )

    def test_unified_capabilities_list_voice_capabilities(self):
        response = self.client.get("/api/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["contract_version"], "capability-runtime-v1")
        capability_ids = {item["capability_id"] for item in payload["capabilities"]}
        self.assertIn("voice.tts.edge", capability_ids)
        self.assertIn("voice.asr.vosk", capability_ids)

    def test_integration_doc_locks_public_contract_boundaries(self):
        doc = Path("docs/myprivateagent-integration.md").read_text(encoding="utf-8")

        self.assertIn("audio/pcm;rate=16000;channels=1;format=s16le", doc)
        self.assertIn("VOICE_RUNTIME_DISABLED", doc)
        self.assertIn("VOICE_PROVIDER_UNAVAILABLE", doc)
        self.assertIn("VOICE_PROVIDER_ERROR", doc)
        self.assertIn('"partial": true', doc)
        self.assertIn("MyPrivateAgent 推荐使用 capability JSON 方式", doc)

    def test_disabled_tts_invoke_returns_structured_error(self):
        response = self.client.post("/api/capabilities/voice.tts.edge/invoke", json={"text": "hello"})

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["capability_id"], "voice.tts.edge")
        self.assertEqual(payload["error"]["code"], "VOICE_RUNTIME_DISABLED")

    def test_unknown_capability_returns_404(self):
        response = self.client.post("/api/capabilities/unknown/invoke", json={})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "CAPABILITY_NOT_FOUND")

    def test_service_contract_can_lookup_one_capability(self):
        capability = VoiceService().get_capability("voice.tts.edge")

        self.assertEqual(capability["kind"], "tts")
        self.assertEqual(capability["provider"], "edge_tts")


if __name__ == "__main__":
    unittest.main()
