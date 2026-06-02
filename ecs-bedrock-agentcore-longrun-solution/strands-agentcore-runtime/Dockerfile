FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN dnf upgrade -y --security && \
    dnf install -y python3.13 python3.13-pip shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

# Install AWS CLI via pip (required by MCP server's call_aws tool)
RUN python3 -m pip install --no-cache-dir awscli

WORKDIR /app

# Install deps at build time (no cold start)
COPY requirements.txt requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy all source including local MCP server (src/)
COPY . .

# Pre-create MCP working directory
RUN mkdir -p /tmp/aws-api-mcp/workdir

ENV AWS_REGION=us-west-2 AWS_DEFAULT_REGION=us-west-2 DOCKER_CONTAINER=1 PYTHONUNBUFFERED=1
ENV PORT=8080

RUN useradd -m -u 1000 bedrock_agentcore && chown -R bedrock_agentcore:bedrock_agentcore /tmp/aws-api-mcp
USER bedrock_agentcore

EXPOSE 8080
CMD ["python3", "-m", "main"]
