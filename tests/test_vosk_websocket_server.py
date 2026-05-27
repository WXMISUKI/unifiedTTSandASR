import json
import logging
import unittest

from app.vosk_websocket_server import VoskStreamingSession, configure_vosk_server_logging


class FakeRecognizer:
    def __init__(self):
        self.words = False
        self.accepted_chunks = []

    def SetWords(self, enabled):
        self.words = enabled

    def AcceptWaveform(self, chunk):
        self.accepted_chunks.append(chunk)
        return chunk == b"final"

    def Result(self):
        return json.dumps({"text": "最终结果"}, ensure_ascii=False)

    def PartialResult(self):
        return json.dumps({"partial": "中间结果"}, ensure_ascii=False)

    def FinalResult(self):
        return json.dumps({"text": "结束结果"}, ensure_ascii=False)


class VoskStreamingSessionTests(unittest.TestCase):
    def test_logging_configuration_suppresses_websocket_handshake_tracebacks(self):
        configure_vosk_server_logging()

        self.assertEqual(logging.getLogger("websockets.server").level, logging.CRITICAL)
        self.assertEqual(logging.getLogger("websockets.asyncio.server").level, logging.CRITICAL)

    def test_audio_chunk_returns_partial_until_final_result(self):
        session = VoskStreamingSession(lambda sample_rate: FakeRecognizer(), sample_rate=16000)

        partial = session.accept_audio(b"partial")
        final = session.accept_audio(b"final")

        self.assertEqual(partial, {"partial": "中间结果"})
        self.assertEqual(final, {"text": "最终结果"})

    def test_config_message_can_override_sample_rate_before_audio(self):
        created_with = []
        session = VoskStreamingSession(lambda sample_rate: created_with.append(sample_rate) or FakeRecognizer(), sample_rate=16000)

        response = session.accept_text('{"config": {"sample_rate": 8000}}')
        session.accept_audio(b"partial")

        self.assertEqual(response, {"ok": True, "sample_rate": 8000})
        self.assertEqual(created_with, [8000])

    def test_eof_message_returns_final_result(self):
        session = VoskStreamingSession(lambda sample_rate: FakeRecognizer(), sample_rate=16000)

        response = session.accept_text('{"eof": 1}')

        self.assertEqual(response, {"text": "结束结果"})


if __name__ == "__main__":
    unittest.main()
