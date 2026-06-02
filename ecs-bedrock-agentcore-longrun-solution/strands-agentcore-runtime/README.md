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
| `MODEL_ID` | no | Bedrock model (default: us.anthropic.claude-3-7-sonnet-20250219-v1:0) |
