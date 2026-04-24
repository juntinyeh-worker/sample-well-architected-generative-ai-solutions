FROM public.ecr.aws/amazonlinux/amazonlinux:2023 AS builder
RUN dnf install -y python3.11 python3.11-pip python3.11-devel gcc gcc-c++ && dnf clean all
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1
WORKDIR /build
COPY requirements.txt .
RUN pip3 install --user --no-cache-dir -r requirements.txt

FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN dnf install -y python3.11 curl shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /root/.local /home/app/.local
COPY . .
RUN chown -R app:app /app
USER app
ENV PATH=/home/app/.local/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
