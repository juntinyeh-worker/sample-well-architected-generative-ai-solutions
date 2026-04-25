# Sample Well-Architected Generative AI Solutions

Sample implementations and reference architectures for building well-architected generative AI solutions on AWS. Each solution demonstrates a different approach to integrating Amazon Bedrock with ECS Fargate for cloud optimization and security assessment workloads.

## Solutions

### 1. ECS + Bedrock Agent Solution

**Path:** [`ecs-bedrock-agent-solution/`](ecs-bedrock-agent-solution/)

Uses **Amazon Bedrock Agents** with MCP (Model Context Protocol) action groups to perform AWS security assessments. The Bedrock Agent orchestrates tool calls to MCP servers that execute AWS API operations on behalf of the user.

- FastAPI backend on ECS Fargate behind ALB + CloudFront
- Bedrock Agent with WA Security MCP action groups
- LLM Orchestrator routes between direct Bedrock Converse API and Agent invocation
- React frontend (CloudScape) with Cognito authentication
- SSM Parameter Store for configuration management

→ See [`ecs-bedrock-agent-solution/SOLUTION_ARCHITECTURE.md`](ecs-bedrock-agent-solution/SOLUTION_ARCHITECTURE.md) for full architecture details.

### 2. ECS + Bedrock AgentCore Runtime Solution

**Path:** [`ecs-bedrock-agentcore-runtime-solution/`](ecs-bedrock-agentcore-runtime-solution/)

Uses **Bedrock AgentCore Runtime** with **Strands Agents** for dynamic agent discovery and invocation. Three specialized agents handle AWS API operations, security assessments, and cost optimization — each running its own embedded MCP server.

- FastAPI backend with shared middleware layer (auth, CORS, logging, validation)
- AgentCore layer for agent discovery, registration, and LLM-based routing
- Three Strands agents: AWS API, WA Security, Cost Optimization
- Graceful degradation when agents or AgentCore Runtime are unavailable
- HTML/JS frontend with prompt template system

→ See [`ecs-bedrock-agentcore-runtime-solution/SOLUTION_ARCHITECTURE.md`](ecs-bedrock-agentcore-runtime-solution/SOLUTION_ARCHITECTURE.md) for full architecture details.

### 3. ECS + Bedrock AgentCore Long-Running Solution

**Path:** [`ecs-bedrock-agentcore-longrun-solution/`](ecs-bedrock-agentcore-longrun-solution/)

An **async orchestrator** that dispatches long-running tasks to Bedrock AgentCore Runtimes (powered by Kiro CLI) and streams results back via WebSocket. Designed for tasks that take seconds to minutes — infrastructure scans, code generation, incident response.

- FastAPI orchestrator with WebSocket support
- 3-tier intent classification (decline / answer directly / route to agent)
- Async task dispatch with parallel execution via `asyncio`
- Kiro CLI wrapper registered as Bedrock AgentCore Runtime
- React frontend (CloudScape) with real-time result streaming
- Demo/sandbox mode with read-only restrictions and output masking

→ See [`ecs-bedrock-agentcore-longrun-solution/SOLUTION_ARCHITECTURE.md`](ecs-bedrock-agentcore-longrun-solution/SOLUTION_ARCHITECTURE.md) for full architecture details.

## Add-On: MCP Servers

**Path:** [`mcp-servers/`](mcp-servers/)

Standalone MCP server implementations with cross-account IAM AssumeRole support. These are used as tool backends by the solutions above, but can also be deployed independently with any MCP-compatible client.

| Server | Description |
|--------|-------------|
| [`aws-api-mcp-server-with-iamrole-support/`](mcp-servers/aws-api-mcp-server-with-iamrole-support/) | Fork of [awslabs/aws-api-mcp-server](https://github.com/awslabs/mcp) with cross-account IAM AssumeRole support. Provides `call_aws` and `suggest_aws_commands` tools for executing AWS CLI operations. |
| [`well-architected-security-mcp-server-with-iamrole-support/`](mcp-servers/well-architected-security-mcp-server-with-iamrole-support/) | Well-Architected Security MCP server with IAM role support. Provides security assessment tools for network security, storage security, security services, and compliance checks. |

## Choosing a Solution

| | Bedrock Agent | AgentCore Runtime | AgentCore Long-Running |
|---|---|---|---|
| **Best for** | Managed agent orchestration | Multi-agent with dynamic discovery | Async tasks that take minutes |
| **Agent framework** | Bedrock Agents API | Strands Agents + AgentCore | Kiro CLI + AgentCore |
| **Communication** | HTTP request/response | HTTP request/response | WebSocket streaming |
| **Scaling** | Single agent with action groups | Multiple specialized agents | Parallel async tasks |
| **Complexity** | Simplest | Most feature-rich | Most flexible |

## Common Stack

All solutions share:
- **Compute**: ECS Fargate on Amazon Linux 2023 (Python 3.12)
- **Frontend**: CloudFront + S3
- **Auth**: Amazon Cognito
- **AI**: Amazon Bedrock (Claude)
- **Config**: SSM Parameter Store
- **CI/CD**: CodeBuild + CodePipeline
- **IaC**: CloudFormation

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
