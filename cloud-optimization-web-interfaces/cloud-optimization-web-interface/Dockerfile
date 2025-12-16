# Build stage
FROM amazonlinux:2023 as builder

RUN dnf update -y --security && dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    gcc-c++ \
    make \
    && dnf clean all

WORKDIR /build
COPY backend/requirements.txt .
RUN pip3.11 install --user --no-cache-dir --upgrade pip && \
    pip3.11 install --user --no-cache-dir -r requirements.txt

# Production stage - Minimal runtime
FROM amazonlinux:2023

RUN dnf update -y --security && \
    dnf install -y python3.11 shadow-utils --setopt=install_weak_deps=False && \
    dnf clean all && \
    rm -rf /var/cache/dnf /tmp/* /var/tmp/* /var/log/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY backend/ .

RUN chown -R appuser:appuser /app && \
    chmod -R 750 /app

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
