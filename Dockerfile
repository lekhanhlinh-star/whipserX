FROM  nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    default-mysql-client \
    ffmpeg \
    git \
    python3-pip \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    software-properties-common && \
    ln -sf python3.11 /usr/bin/python && \
    ln -sf pip3 /usr/bin/pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --ignore-installed --upgrade pip setuptools && \
    pip install  --ignore-installed -r requirements.txt
COPY . .
# RUN python -m whisperx large-v2 
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["python", "runpod_handle.py"]