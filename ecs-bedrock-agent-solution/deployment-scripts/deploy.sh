#!/bin/bash
set -e

STACK_NAME="${STACK_NAME:-cloud-optimization-assistant}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

usage() {
  echo "Usage: $0 <backend|frontend|all> [--stack-name NAME] [--region REGION]"
  exit 1
}

[[ $# -lt 1 ]] && usage

TARGET="$1"; shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --region)     REGION="$2"; shift 2 ;;
    *)            usage ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

deploy_backend() {
  local bucket
  bucket=$(get_output BackendSourceBucketName)
  echo "📦 Packaging backend..."
  (cd "$PROJECT_DIR/ecs-backend" && zip -rq /tmp/backend-source.zip .)
  echo "⬆️  Uploading to s3://$bucket/source.zip"
  aws s3 cp /tmp/backend-source.zip "s3://$bucket/source.zip" --region "$REGION"
  rm -f /tmp/backend-source.zip
  echo "✅ Backend pipeline triggered"
}

deploy_frontend() {
  local bucket
  bucket=$(get_output FrontendSourceBucketName)
  echo "📦 Packaging frontend..."
  (cd "$PROJECT_DIR/frontend-react" && zip -rq /tmp/frontend-source.zip . -x "node_modules/*" "dist/*" ".git/*")
  echo "⬆️  Uploading to s3://$bucket/source.zip"
  aws s3 cp /tmp/frontend-source.zip "s3://$bucket/source.zip" --region "$REGION"
  rm -f /tmp/frontend-source.zip
  echo "✅ Frontend pipeline triggered"
}

case "$TARGET" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend ;;
  all)      deploy_backend; deploy_frontend ;;
  *)        usage ;;
esac
