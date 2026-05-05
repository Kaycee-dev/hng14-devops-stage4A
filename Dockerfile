FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/ /app/

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=6 \
    CMD python -c "import os, sys, urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('APP_PORT','3000') + '/healthz', timeout=2).status == 200 else 1)" \
    || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
