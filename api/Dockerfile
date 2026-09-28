# 빌드 컨텍스트는 저장소 루트 (docker-compose.yml 참고)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PROJECT_ROOT=/app

WORKDIR /app

# torch는 requirements.txt와 같은 버전의 CPU 빌드를 먼저 설치한다 (CUDA 빌드는 수 GB)
COPY requirements.txt .
RUN pip install "$(grep -E '^torch==' requirements.txt | sed 's/[[:space:]].*//')" \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-deps -e .

COPY configs/ configs/
COPY api/ api/

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
