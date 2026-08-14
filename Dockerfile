FROM python:3.14-slim

WORKDIR /app

# Keep this FIRST. The base image's bundled pip crashes while computing its User-Agent
# under linux/arm64 QEMU when poetry shells out to it. Upgrading pip before installing
# poetry avoids it — this cost Lenticularis a release.
RUN pip install --no-cache-dir --upgrade pip setuptools

RUN pip install --no-cache-dir poetry==2.4.1

COPY pyproject.toml poetry.lock* README.md ./
# --extras importer: python -m flightlog.core.importer is a shipped v0.2 feature and must
# run inside the container, not just under pytest — openpyxl is not part of the base
# dependency set (see pyproject.toml).
# --extras igc: v0.5's IGC analysis (api/routers/igc.py) needs libigc at runtime, not just
# under pytest. Both libigc and its transitive simplekml dependency ship as pure-Python
# (libigc a universal py3-none-any wheel; simplekml an sdist with no compiled extension), so
# this doesn't reintroduce the QEMU/arm64 compilation risk the pip-upgrade step above guards
# against — confirmed via PyPI's file metadata before adding this, not assumed.
RUN poetry config virtualenvs.create false \
    && poetry lock \
    && poetry install --only main --extras importer --extras igc --no-interaction --no-ansi --no-root

COPY src/ ./src/
COPY static/ ./static/
COPY config.yml.example ./config.yml.example

RUN mkdir -p /app/data /app/data/igc /app/logs

ENV PYTHONPATH=/app/src \
    CONFIG_PATH=/app/config.yml \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# slim images ship no curl — use the stdlib.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "flightlog.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
