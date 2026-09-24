FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" --retries 3 --timeout 30 --require-hashes -r requirements.lock

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
