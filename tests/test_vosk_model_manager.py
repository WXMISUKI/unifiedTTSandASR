import tempfile
import unittest
import zipfile
from pathlib import Path

from app.vosk_model_manager import DEFAULT_MODEL_NAME, DEFAULT_MODELS, extract_model_zip, resolve_model_url


class VoskModelManagerTests(unittest.TestCase):
    def test_default_chinese_model_has_download_url(self):
        self.assertEqual(DEFAULT_MODEL_NAME, "vosk-model-small-cn-0.22")
        self.assertIn(DEFAULT_MODEL_NAME, DEFAULT_MODELS)
        self.assertTrue(resolve_model_url(DEFAULT_MODEL_NAME).endswith(f"{DEFAULT_MODEL_NAME}.zip"))

    def test_extract_model_zip_returns_extracted_model_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            zip_path = base / "model.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("vosk-model-small-cn-0.22/README", "model")

            model_dir = extract_model_zip(zip_path, base / "models", "vosk-model-small-cn-0.22")

            self.assertEqual(model_dir, base / "models" / "vosk-model-small-cn-0.22")
            self.assertTrue((model_dir / "README").exists())


if __name__ == "__main__":
    unittest.main()
