"""Streamlit entrypoint for the active KB-C dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dashboard.kbc_daily_dashboard import render_dashboard


def main() -> None:
    render_dashboard()


if __name__ == "__main__":
    main()
