# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM public.ecr.aws/amazonlinux/amazonlinux:2023 AS uv

RUN dnf install -y python3.13 python3.13-pip python3.13-devel gcc gcc-c++ make libffi-devel openssl-devel && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_PREFERENCE=only-system
ENV UV_FROZEN=true

COPY pyproject.toml uv.lock uv-requirements.txt ./

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install uv via pip, then install dependencies
RUN pip3.13 install --no-cache-dir --require-hashes --requirement uv-requirements.txt && \
    uv sync --python 3.13 --frozen --no-install-project --no-dev --no-editable

COPY . /app
RUN uv sync --python 3.13 --frozen --no-dev --no-editable

RUN mkdir -p /root/.local

FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN dnf install -y python3.13 ca-certificates shadow-utils && dnf clean all && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN groupadd -r app && useradd -r -g app -d /app app

COPY --from=uv --chown=app:app /app/.venv /app/.venv

COPY ./docker-healthcheck.sh /usr/local/bin/docker-healthcheck.sh

USER app

HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 CMD ["docker-healthcheck.sh"]
ENTRYPOINT ["awslabs.aws-api-mcp-server"]
