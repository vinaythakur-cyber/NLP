# syntax=docker/dockerfile:1
# CPU image by default (small). For a GPU image:
#   docker build --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126 -t lingua-bridge:gpu .
#   docker run --gpus all ...   (needs the NVIDIA Container Toolkit on the host)
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG EXTRAS=api,translate
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
# PyTorch first, from the chosen index, so the next step does not pull the multi-GB default build.
RUN case ",$EXTRAS," in *,translate,*) pip install torch --index-url "$TORCH_INDEX" ;; esac
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[$EXTRAS]"

FROM python:${PYTHON_VERSION}-slim
RUN useradd --create-home --uid 10001 lingua && mkdir /models && chown lingua /models
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    LB_HOST=0.0.0.0 \
    LB_PORT=8000 \
    LB_WEB_DIR=/app/web
WORKDIR /app
COPY web ./web
USER lingua
# Model weights are NOT in the image: they download on first use into this volume.
VOLUME /models
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["lingua", "serve"]
