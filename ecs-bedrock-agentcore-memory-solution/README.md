# ECS Bedrock AgentCore Memory Solution

A full-stack async conversational orchestrator with **AgentCore Memory** — everything from the [longrun-solution](../ecs-bedrock-agentcore-longrun-solution/) plus integrated short-term and long-term memory for cross-session context retention.

## What's Different from longrun-solution

This solution adds:
- `AWS::BedrockAgentCore::Memory` resource with semantic + summarization strategies
- `MEMORY_ID` env var wired to the AgentCore Runtime
- Memory API permissions on the Runtime IAM role
- `--memory-name` and `--event-expiry-days` deploy parameters

Everything else (ECS, CloudFront, ALB, CodeBuild, Cognito, task logging) is identical.

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
                              │  Claude   │ │ Runtime │ │  Memory    │
                              │  (Intent) │ │ (Kiro)  │ │            │
                              └───────────┘ └────┬────┘ └─────▲─────┘
                                                 │            │
                                                 └────────────┘
                                              MEMORY_ID env var
                                              auto read/write turns
```

### Memory Flow

1. User sends message → Orchestrator dispatches to AgentCore Runtime
2. Runtime reads long-term memory (facts, summaries) for context
3. Runtime executes task with Kiro CLI
4. Runtime writes conversation turns as events (short-term memory)
5. Memory service extracts insights into long-term memory:
   - **Semantic** → `/facts/{actorId}/` (extracted facts)
   - **Summarization** → `/summaries/{actorId}/{sessionId}/` (session summaries)

## Deploy

```bash
cd deployment-scripts

# Full deploy with memory
python deploy.py \
  --stack-name agentcore-memory-demo \
  --region us-west-2 \
  --environment dev \
  --memory-name AgentMemory \
  --event-expiry-days 30 \
  --demo-mask-output true \
  --demo-read-only true

# After deploy, set the API key
aws ssm put-parameter \
  --name /agentcore-memory-demo/kiro-api-key \
  --value "your-api-key" \
  --type SecureString --overwrite \
  --region us-west-2
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `--stack-name` | `agentcore-longrun-memory` | CloudFormation stack name |
| `--region` | `us-west-2` | AWS region |
| `--environment` | `prod` | Environment (dev/staging/prod) |
| `--memory-name` | `AgentMemory` | Memory resource name |
| `--event-expiry-days` | `30` | Short-term memory retention (3–365 days) |
| `--demo-mask-output` | `false` | Mask resource IDs in output |
| `--demo-read-only` | `false` | Restrict to read-only operations |
| `--phase` | `all` | Deploy phase (infra/build/update/all) |

## Stack Resources (38)

Everything from longrun-solution (36 resources) plus:

| Resource | Type | Description |
|---|---|---|
| `AgentCoreMemory` | `AWS::BedrockAgentCore::Memory` | Memory with semantic + summarization strategies |

The AgentCore Runtime is updated with:
- `MEMORY_ID` env var → Memory resource ID
- IAM permissions for memory API operations

## Stack Outputs

| Output | Description |
|---|---|
| `CloudFrontURL` | Frontend URL |
| `ALBDnsName` | Backend ALB |
| `MemoryId` | AgentCore Memory ID |
| `MemoryArn` | AgentCore Memory ARN |
| `AgentCoreRuntimeArn` | Runtime ARN |
| `SourceBucket` | Source code bucket |
| `KiroApiKeySSMParam` | SSM parameter path |
| *(+ all longrun outputs)* | |

## Files

```
ecs-bedrock-agentcore-memory-solution/
├── deployment-scripts/
│   ├── agentcore-longrun-orchestrator-0.1.0.yaml  # CFN template (v0.2.0 with Memory)
│   ├── deploy.py                                   # Deploy script with memory params
│   └── buildspecs/                                 # CodeBuild specs
├── ecs-backend/                                    # FastAPI orchestrator
├── frontend-react/                                 # CloudScape React UI
├── kiro-agentcore-runtime/                         # Kiro CLI ACP wrapper
├── docs/
├── SOLUTION_ARCHITECTURE.md
└── README.md
```
