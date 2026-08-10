"""Deterministic KDRI 2025 nutrient dose engine."""

DATA_DIR = __import__("pathlib").Path(__file__).resolve().parents[2] / "data"
VENDOR_DIR = DATA_DIR / "vendor"
CURATED_DIR = DATA_DIR / "curated"
