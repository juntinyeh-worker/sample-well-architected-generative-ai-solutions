#!/bin/bash
# test-build-dockerfiles.sh
# Validates all 6 AL2023 Dockerfiles by building them locally.
# Run from the repo root: ./test-build-dockerfiles.sh
set -euo pipefail

PASS=0
FAIL=0
RESULTS=""

build() {
  local name="$1" dockerfile="$2" context="$3"
  echo "========================================"
  echo "Building: $name"
  echo "  Dockerfile: $dockerfile"
  echo "  Context:    $context"
  echo "========================================"
  if docker build -f "$dockerfile" -t "test-al2023-${name}" "$context" 2>&1; then
    echo "✅ $name: PASS"
    RESULTS="${RESULTS}\n✅ $name"
    PASS=$((PASS + 1))
  else
    echo "❌ $name: FAIL"
    RESULTS="${RESULTS}\n❌ $name"
    FAIL=$((FAIL + 1))
  fi
  echo ""
}

build "longrun-ecs-backend" \
  "ecs-bedrock-agentcore-longrun-solution/ecs-backend/deployment/Dockerfile" \
  "ecs-bedrock-agentcore-longrun-solution/ecs-backend/"

build "longrun-kiro-agentcore" \
  "ecs-bedrock-agentcore-longrun-solution/kiro-agentcore-runtime/Dockerfile" \
  "ecs-bedrock-agentcore-longrun-solution/kiro-agentcore-runtime/"

build "runtime-agentcore" \
  "ecs-bedrock-agentcore-runtime-solution/ecs-backend/deployment/agentcore.dockerfile" \
  "ecs-bedrock-agentcore-runtime-solution/ecs-backend/"

build "strands-aws-api" \
  "ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-aws-api/Dockerfile" \
  "ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-aws-api/"

build "strands-wa-sec" \
  "ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-wa-sec/Dockerfile" \
  "ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-wa-sec/"

build "mcp-server" \
  "mcp-servers/aws-api-mcp-server-with-iamrole-support/Dockerfile" \
  "mcp-servers/aws-api-mcp-server-with-iamrole-support/"

echo ""
echo "========================================"
echo "RESULTS: $PASS passed, $FAIL failed"
echo "========================================"
echo -e "$RESULTS"

exit $FAIL
