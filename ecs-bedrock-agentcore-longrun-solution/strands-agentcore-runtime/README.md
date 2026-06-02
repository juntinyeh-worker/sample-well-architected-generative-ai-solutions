# Strands Agent as AgentCore Runtime

Uses Strands Agents + Bedrock + aws-api-mcp-server as a Bedrock AgentCore Runtime. No external API keys required — uses IAM task role only.

## How it works

```
invoke_agent_runtime(payload={"input": "check my S3 buckets"})
    → AgentCore container (port 8080)
        → main.py receives HTTP POST (BedrockAgentCoreApp)
            → Strands supervisor_agent routes to aws_api_agent
                → aws_api_agent spawns awslabs.aws-api-mcp-server as MCP subprocess
                    → MCP tools (call_aws, suggest_aws_commands) execute AWS CLI
            → result returned as JSON response
```

## vs kiro-agentcore-runtime

| Aspect | kiro-agentcore-runtime | strands-agentcore-runtime |
|--------|----------------------|--------------------------|
| AI Engine | Kiro CLI subprocess | Strands Agent + BedrockModel |
| Auth | KIRO_API_KEY required | IAM role only |
| MCP tools | via kiro built-in MCP | via strands MCPClient |
| Image size | Heavy (kiro + uv + aws-cli) | Lean (python + pip) |
| Cross-account | Via MCP server env vars | Same |

## Build & Deploy

```bash
# Build
docker build -t strands-agentcore:latest .

# Push to ECR
aws ecr create-repository --repository-name strands-agentcore --region us-west-2
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
docker tag strands-agentcore:latest $ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/strands-agentcore:latest
docker push $ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/strands-agentcore:latest

# Register as AgentCore runtime
python3 deploy_runtime.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | auto | AWS region (provided by AgentCore task role) |
| `MODEL_ID` | no | Bedrock model (default: anthropic.claude-opus-4-6-v1) |
| `MODEL_ID_SSM_PARAM` | no | SSM parameter path to override model ID at runtime |
| `STEERING_PATH` | no | Local path to steering .md files (default: /app/steering) |
| `STEERING_S3_URI` | no | S3 URI to load steering files from (e.g. s3://bucket/steering/) |

## Steering Files (WA Review Flow)

The agent loads kiro-style steering files (.md) to guide its behavior. These are injected into the system prompt on each request.

### Structure
```
steering/
├── product.md              # Agent identity and output format
├── flow.md                 # Review process steps
└── pillars/                # Per-pillar check definitions
    ├── security.md         # SEC-01 through SEC-08
    ├── reliability.md      # REL-01 through REL-05
    ├── cost.md             # COST-01 through COST-05
    └── operational-excellence.md  # OPS-01 through OPS-04
```

### Loading Priority
1. `STEERING_S3_URI` — load from S3 (allows updates without rebuild)
2. `STEERING_PATH` — load from local filesystem (baked into image)

### Custom Steering
To customize the review flow, either:
- Replace files in `steering/` before building the image
- Upload to S3 and set `STEERING_S3_URI` env var on the runtime
