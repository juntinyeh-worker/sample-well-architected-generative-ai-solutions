# ECS Bedrock AgentCore Long-Running Solution

Async conversational orchestrator that dispatches long-running tasks to Bedrock AgentCore Runtimes and streams results back to users via WebSocket.

## Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────────┐
│  CloudScape UI  │◄──────────────────►│  ECS Fargate         │
│  (CloudFront)   │                    │  FastAPI Orchestrator │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              ┌───────────┐ ┌─────────┐ ┌───────────┐
                              │  Bedrock  │ │AgentCore│ │ AgentCore │
                              │  Claude   │ │Runtime 1│ │ Runtime N │
                              │  (Intent) │ │         │ │           │
                              └───────────┘ └─────────┘ └───────────┘
```

## Key Features

- **Async task dispatch** — AI acknowledges immediately, runs tasks in background
- **Parallel execution** — Multiple tasks run simultaneously via `asyncio.create_task()`
- **WebSocket streaming** — Real-time push when results arrive
- **Progressive disclosure** — Brief summary first, full detail on request

## Components

| Directory | Description |
|-----------|-------------|
| `ecs-backend/` | FastAPI orchestrator with WebSocket, intent parsing, AgentCore invocation |
| `frontend-react/` | CloudScape-based chat UI (pre-built dist/) |
| `deployment-scripts/` | CloudFormation template, deploy script, buildspecs |
| `kiro-agentcore-runtime/` | Custom AgentCore runtime wrapper (Dockerfile + deploy script) |
| `docs/` | Architecture documentation |

## Prerequisites

- AWS account with Bedrock access
- A deployed AgentCore Runtime (ARN required)
- Python 3.11+
- Docker (for container builds)

## Quick Start

```bash
cd deployment-scripts
python deploy.py \
  --stack-name agentcore-longrun \
  --region us-west-2 \
  --runtime-arn arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/YOUR_RUNTIME_ID
```

## Local Development

```bash
cd ecs-backend
pip install -r requirements.txt
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/ID"
uvicorn main:app --reload --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTCORE_RUNTIME_ARN` | ARN of the AgentCore Runtime | (required) |
| `BEDROCK_REGION` | Region for Bedrock model calls | us-west-2 |
| `MODEL_ID` | Bedrock model for intent parsing | anthropic.claude-3-haiku-20240307-v1:0 |
| `PORT` | Server port | 8000 |

## License

MIT-0 — See [LICENSE](../LICENSE).
