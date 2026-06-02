# AWS API MCP Server (Local Bundle)

This `src/` directory is a bundled copy of the modified `awslabs.aws-api-mcp-server` with cross-account AssumeRole support.

## Why bundled locally?

1. **No cold start** — pre-installed in Docker image at build time
2. **Credential passthrough** — enhanced `credential_utils.py` explicitly passes IAM task role credentials to the MCP subprocess via environment variables (solving the known issue where subprocess doesn't inherit AgentCore task role)

## Source

Copied from:
```
ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-aws-api/src/
```

## Setup

Copy the `core/` directory from the runtime-solution source:

```bash
cp -r ../../../ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-aws-api/src/core ./src/core
```

Or from the GitHub repo:
```
https://github.com/aws-samples/sample-well-architected-generative-ai-solutions/tree/main/ecs-bedrock-agentcore-runtime-solution/strands-agents/strands-aws-api/src/core
```

## Structure

```
src/
├── __init__.py
├── __main__.py
├── server.py          # FastMCP server with call_aws, suggest_aws_commands tools
├── run_server.py
└── core/              # ← Copy from runtime-solution
    ├── agent_scripts/ # Execution plan scripts
    ├── aws/           # AWS CLI driver, service layer
    ├── common/        # Config, errors, helpers, credential_utils (AssumeRole)
    ├── data/          # Static data files
    ├── metadata/      # Read-only operations list
    ├── parser/        # CLI command parser
    └── security/      # Security policy enforcement
```
