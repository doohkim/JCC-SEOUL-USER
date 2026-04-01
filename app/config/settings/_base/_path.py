from pathlib import Path

__all__ = (
    "BASE_DIR",
    "ROOT_DIR",
    "STATIC_DIR",
    "TEMPLATES_DIR",
    "LIBRARY_TEMPLATES_DIR",
    "VIEWS_TEMPLATES_DIR",
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ROOT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
LIBRARY_TEMPLATES_DIR = TEMPLATES_DIR / "library"
VIEWS_TEMPLATES_DIR = TEMPLATES_DIR / "views"
