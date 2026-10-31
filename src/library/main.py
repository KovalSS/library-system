"""Точка входу для uvicorn: `python -m uvicorn library.main:app --app-dir src`."""
from library.app import create_app

app = create_app()
