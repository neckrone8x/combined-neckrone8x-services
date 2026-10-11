FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir \
      fastapi "uvicorn[standard]" \
      pydantic pydantic-settings \
      httpx arxiv qdrant-client \
      rank-bm25 sqlalchemy psycopg2-binary tqdm

COPY app ./app
COPY static ./static

ENV NECKRONE_LOAD_LOCAL_MODELS=false
ENV PORT=8001

EXPOSE 8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]