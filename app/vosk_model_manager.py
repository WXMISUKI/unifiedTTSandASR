"""Helpers for downloading and extracting Vosk model assets."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_MODEL_NAME = "vosk-model-small-cn-0.22"
DEFAULT_MODELS = {
    DEFAULT_MODEL_NAME: "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
}


def resolve_model_url(model_name: str) -> str:
    try:
        return DEFAULT_MODELS[model_name]
    except KeyError as exc:
        supported = ", ".join(sorted(DEFAULT_MODELS))
        raise ValueError(f"Unsupported model '{model_name}'. Supported models: {supported}") from exc


def extract_model_zip(zip_path: Path, output_dir: Path, model_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(output_dir)
    model_dir = output_dir / model_name
    if not model_dir.exists():
        candidates = [path for path in output_dir.iterdir() if path.is_dir() and path.name.startswith("vosk-model")]
        if len(candidates) == 1:
            candidates[0].rename(model_dir)
    if not model_dir.exists():
        raise FileNotFoundError(f"Extracted model directory was not found: {model_dir}")
    return model_dir


def download_model(*, model_name: str, output_dir: Path, force: bool = False) -> Path:
    model_dir = output_dir / model_name
    if model_dir.exists() and not force:
        return model_dir
    if model_dir.exists() and force:
        shutil.rmtree(model_dir)

    url = resolve_model_url(model_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / f"{model_name}.zip"
        urllib.request.urlretrieve(url, zip_path)
        return extract_model_zip(zip_path, output_dir, model_name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a Vosk model into the local models directory.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--output-dir", default="models")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    model_dir = download_model(
        model_name=args.model_name,
        output_dir=Path(args.output_dir).resolve(),
        force=args.force,
    )
    print(f"Vosk model ready: {model_dir}")


if __name__ == "__main__":
    main()
