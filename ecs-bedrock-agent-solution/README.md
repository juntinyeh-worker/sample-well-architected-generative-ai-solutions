# ECS Bedrock Agent Solution

Cloud Optimization Assistant built on Amazon Bedrock Agents, running on ECS Fargate with MCP (Model Context Protocol) server integration for AWS security and cost analysis.

## Architecture

```
┌─────────────┐      ┌──────────────────────────────────────┐
│  Frontend   │      │  ECS Fargate (FastAPI)               │
│  (React/JS) │◄────►│  ┌────────────┐  ┌────────────────┐ │
└─────────────┘ REST │  │ LLM        │  │ Bedrock Agent  │ │
                + WS │  │ Orchestrator│─►│ Service        │ │
                     │  └────────────┘  └───────┬────────┘ │
                     │                          │          │
                     │              ┌───────────┼──────┐   │
                     │              ▼           ▼      ▼   │
                     │         ┌────────┐ ┌────────┐ ┌───┐ │
                     │         │Bedrock │ │MCP     │ │SSM│ │
                     │         │Agent   │ │Client  │ │   │ │
                     │         └────────┘ └────────┘ └───┘ │
                     └──────────────────────────────────────┘
```

## Components

| Directory | Description |
|-----------|-------------|
| `bedrock-agents/` | Bedrock Agent configurations — single-MCP and multi-MCP variants |
| `deployment-scripts/` | CloudFormation template, deploy scripts, Cognito setup, buildspecs |
| `ecs-backend/` | FastAPI backend with Bedrock Agent and LLM orchestrator services |
| `frontend/` | Vanilla JS frontend with Cognito auth |
| `frontend-react/` | React frontend alternative |
| `docs/` | Architecture diagrams, Cognito, cross-account, and Parameter Store guides |

## Prerequisites

- AWS account with Amazon Bedrock access
- Python 3.11+
- Node.js (for frontend builds)

## Deployment

See [deployment-scripts/README.md](deployment-scripts/README.md) for full instructions.

## Documentation

- [Deployment Scripts](deployment-scripts/README.md) — Deploy scripts and CloudFormation
- [ECS Backend](ecs-backend/README.md) — Backend architecture and integration guide
- [Docs](docs/README.md) — Architecture, auth, cross-account, and config guides

## License

MIT-0 — See [LICENSE](../LICENSE).
