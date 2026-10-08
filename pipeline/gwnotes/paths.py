from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PIPELINE_ROOT.parent
SHARED = REPO_ROOT / "shared"
FONT_GENERATED = SHARED / "font" / "generated"
