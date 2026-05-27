"""Command wrapper for downloading Vosk model assets."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vosk_model_manager import main


if __name__ == "__main__":
    main()
