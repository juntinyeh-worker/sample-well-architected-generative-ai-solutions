FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN dnf install -y python3.11 python3.11-pip python3.11-devel gcc gcc-c++ shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3.11 install --no-cache-dir -r requirements.txt
RUN pip3.11 install --no-cache-dir aws-opentelemetry-distro>=0.10.1

ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1
ENV DOCKER_CONTAINER=1

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080
EXPOSE 8000

COPY . .

CMD ["opentelemetry-instrument", "python3", "-m", "main"]
