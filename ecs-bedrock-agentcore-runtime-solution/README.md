# ECS Bedrock AgentCore Runtime Solution

Cloud Optimization Assistant using Bedrock AgentCore Runtime with Strands-based agents on ECS Fargate. Supports AWS API operations, cost optimization analysis, and Well-Architected security assessments.

## Architecture

```
┌──────────────┐      ┌──────────────────────────────────────────┐
│  Frontend    │      │  ECS Fargate (FastAPI)                   │
│  (S3 + CF)  │◄────►│  AgentCore Runtime Backend               │
└──────────────┘      │  ┌─────────────────────────────────────┐ │
                      │  │ Agent Discovery & Invocation        │ │
                      │  └──────────┬──────────────────────────┘ │
                      │             │                             │
                      │  ┌──────────┼──────────┬───────────┐     │
                      │  ▼          ▼          ▼           │     │
                      │ strands-   strands-   strands-     │     │
                      │ aws-api   aws-cost   wa-sec        │     │
                      └──────────────────────────────────────────┘
```

## Components

| Directory | Description |
|-----------|-------------|
| `strands-agents/` | Three Strands-based agents: AWS API, Cost Optimization, WA Security |
| `deployment-scripts/` | CloudFormation template, deploy script, agent registration tools |
| `ecs-backend/` | FastAPI backend with AgentCore runtime, agent discovery, and invocation |
| `frontend/` | Web interface with Cognito auth and prompt templates |
| `docs/` | Architecture, auth, cross-account, and config guides |

## Prerequisites

- AWS account with Bedrock access
- Python 3.11+
- Docker (for container builds)

## Quick Start

```bash
# Deploy the stack
cd deployment-scripts
python3 deploy_chatbot_stack.py --stack-name coa --region us-east-1

# Register agents
cd register-agentcore-runtime
./register_agent.sh
```

See [deployment-scripts/README.md](deployment-scripts/README.md) for full instructions.

## Documentation

- [Deployment Scripts](deployment-scripts/README.md) — Deploy and register agents
- [Agent Registration](deployment-scripts/register-agentcore-runtime/README.md) — Register Strands agents with AgentCore
- [Docs](docs/README.md) — Architecture, auth, cross-account, and config guides

## License

MIT-0 — See [LICENSE](../LICENSE).
