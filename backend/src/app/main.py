"""Punto de entrada ASGI que importa Uvicorn."""

from app.bootstrap import create_app

app = create_app()
