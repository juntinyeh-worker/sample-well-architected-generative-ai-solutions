# ECS Bedrock AgentCore Long-Running Solution

An async conversational orchestrator that dispatches long-running tasks to Bedrock AgentCore Runtimes and streams results back to users via WebSocket.

## Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────────┐
│  CloudScape UI  │◄──────────────────►│  ECS Fargate         │
│  (CloudFront)   │                    │  FastAPI Orchestrator │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    │             │             │
                              ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
                              │  Bedrock  │ │AgentCore│ │  AgentCore │
                              │  Claude   │ │Runtime 1│ │  Runtime N │
                              │  (Intent) │ │         │ │            │
                              └───────────┘ └─────────┘ └────────────┘
```

## Key Features

- **Async task dispatch** — User sends request, AI acknowledges immediately, runs task in background
- **Parallel execution** — Multiple tasks run simultaneously via `asyncio.create_task()`
- **Progressive disclosure** — Brief summary first, full detail on request
- **WebSocket streaming** — Real-time push when results arrive
- **AgentCore Runtime integration** — Tasks are dispatched to Bedrock AgentCore Runtimes

## User Experience Flow

```
User: Check my CloudFormation stacks
AI:   Sure, let me check that for you.
      ... (runs in background via AgentCore Runtime) ...
AI:   Result ready: Hello World!
      Would you like the full detail?
User: yes
AI:   [full detail response]
```

## Components

| Component | Description |
|-----------|-------------|
| `ecs-backend/` | FastAPI orchestrator with WebSocket, intent parsing, AgentCore invocation |
| `frontend-react/` | CloudScape-based chat UI (pre-built dist/) |
| `deployment-scripts/` | CloudFormation template, deploy script, buildspecs |
| `docs/` | Architecture documentation |

## Prerequisites

- AWS Account with Bedrock access
- Python 3.11+
- AWS CLI configured

## Deployment

The solution uses a two-stack model to work within restricted IAM permission boundaries:

| Stack | Template | Requires | Creates |
|-------|----------|----------|---------|
| `*-prereqs` | `prerequisites.yaml` | `iam:CreateRole`, `bedrock-agentcore:CreateWorkloadIdentity` | IAM roles, AgentCore runtime |
| main | `orchestrator-0.2.0.yaml` | Standard deploy permissions (no IAM creation) | VPC, ECS, ALB, CloudFront, CodeBuild |

### Full deploy (admin — has iam:CreateRole)

```bash
cd deployment-scripts
python deploy.py \
  --stack-name sandbox-longrun \
  --region us-west-2 \
  --kiro-api-key "ksk_..." \
  --demo-mask-output true \
  --demo-read-only true
```

The script automatically creates the prerequisites stack, builds the backend image, and deploys the orchestrator.

### Restricted deploy (no iam:CreateRole)

If the prerequisites stack already exists, the script reuses it:

```bash
python deploy.py --stack-name sandbox-longrun --region us-west-2
```

Or pass existing role ARNs directly:

```bash
python deploy.py \
  --stack-name sandbox-longrun \
  --region us-west-2 \
  --task-execution-role-arn arn:aws:iam::ACCOUNT:role/EXEC_ROLE \
  --task-role-arn arn:aws:iam::ACCOUNT:role/TASK_ROLE \
  --build-role-arn arn:aws:iam::ACCOUNT:role/BUILD_ROLE \
  --runtime-arn arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/ID
```

## Local Development

```bash
cd ecs-backend
pip install -r requirements.txt
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/ID"
export BEDROCK_REGION="us-west-2"
uvicorn main:app --reload --port 8000
```

## Testing

```bash
cd ecs-backend
pip install -r tests/requirements-test.txt
pytest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTCORE_RUNTIME_ARN` | ARN of the AgentCore Runtime | (required) |
| `BEDROCK_REGION` | Region for Bedrock model calls | us-west-2 |
| `AGENTCORE_REGION` | Region for AgentCore Runtime | us-west-2 |
| `MODEL_ID` | Bedrock model for intent parsing | anthropic.claude-3-haiku-20240307-v1:0 |
| `PORT` | Server port | 8000 |

## License

MIT-0
