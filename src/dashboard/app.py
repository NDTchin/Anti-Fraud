"""Streamlit entrypoint for the active KB-C dashboard."""

from __future__ import annotations

from src.dashboard.kbc_daily_dashboard import render_dashboard


def main() -> None:
    render_dashboard()


if __name__ == "__main__":
    main()
