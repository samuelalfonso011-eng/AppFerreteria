"""Función Python de Vercel: expone la app Flask de backend/ como WSGI.

vercel.json reescribe /api/:path* hacia esta función; Flask recibe la ruta original y la resuelve con
sus blueprints. El frontend estático lo sirve Vercel desde dist/ (scripts/build-vercel.mjs).

La configuración llega por variables de entorno del proyecto en Vercel (DATABASE_URL del Session
pooler de Supabase, SECRET_KEY, TRUSTED_HOSTS, ...). Ver VERCEL.md.
"""
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND)

from app import create_app  # noqa: E402

app = create_app(os.getenv("FLASK_ENV", "production"))
