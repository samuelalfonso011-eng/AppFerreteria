# syntax=docker/dockerfile:1
# FerrePro: backend Flask + frontend estatico en una sola imagen.
# El contexto es la raiz del repositorio porque Flask sirve index.html y admin.html desde ahi.

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/ferrepro
RUN useradd --system --uid 10001 --no-create-home ferrepro
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn==23.0.0

# Frontend: solo los archivos que Flask tiene en su lista blanca
COPY index.html admin.html styles.css theme.css admin.css app.js admin.js theme-init.js ./
COPY backend/run.py backend/run.py
COPY backend/app backend/app
WORKDIR /srv/ferrepro/backend


# Pruebas: docker compose --profile test run --rm tests
FROM base AS test
COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install -r requirements-dev.txt
COPY backend/tests tests
USER ferrepro
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]


# Ejecucion: gunicorn como usuario sin privilegios, codigo de solo lectura (propiedad de root)
FROM base AS runtime
ENV FLASK_ENV=production \
    FLASK_APP=run.py \
    WEB_CONCURRENCY=2
USER ferrepro
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/store', timeout=4)"]
# Varios workers son seguros: la invalidacion de cache usa el token compartido de la base de datos
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY} --threads 4 --timeout 30 --access-logfile - run:app"]
