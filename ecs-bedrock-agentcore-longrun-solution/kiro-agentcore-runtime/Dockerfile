# Kiro CLI + MCP as AgentCore Runtime (ARM64)
FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y curl bash unzip coreutils && rm -rf /var/lib/apt/lists/*

# Install Kiro CLI via official installer
ENV HOME=/root
RUN curl -fsSL https://cli.kiro.dev/install | bash
ENV PATH="/root/.local/bin:$PATH"

# Verify installation
RUN kiro-cli --version

# Copy the HTTP/ACP wrapper
COPY wrapper.py /app/wrapper.py

ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "/app/wrapper.py"]
