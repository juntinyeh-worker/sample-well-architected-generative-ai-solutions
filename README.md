# Sample Well-Architected Generative AI Solutions

Sample implementations and reference architectures for building well-architected generative AI solutions on AWS.

## Solutions

| Solution | Description |
|----------|-------------|
| [ecs-bedrock-agent-solution](ecs-bedrock-agent-solution/) | Cloud Optimization Assistant using Amazon Bedrock Agents on ECS Fargate with MCP server integration |
| [ecs-bedrock-agentcore-runtime-solution](ecs-bedrock-agentcore-runtime-solution/) | Cloud Optimization Assistant using Bedrock AgentCore Runtime with Strands agents on ECS Fargate |
| [ecs-bedrock-agentcore-longrun-solution](ecs-bedrock-agentcore-longrun-solution/) | Async conversational orchestrator dispatching long-running tasks to Bedrock AgentCore Runtimes via WebSocket |
| [mcp-servers](mcp-servers/) | Forked MCP server implementations with cross-account IAM AssumeRole support |

## Repository Structure

```
.
├── ecs-bedrock-agent-solution/             # Bedrock Agent + MCP on ECS
│   ├── bedrock-agents/                     # Agent configurations (single & multi-MCP)
│   ├── deployment-scripts/                 # CloudFormation, deploy scripts, buildspecs
│   ├── ecs-backend/                        # FastAPI backend with Bedrock Agent integration
│   ├── frontend/                           # Vanilla JS frontend
│   ├── frontend-react/                     # React frontend
│   └── docs/                               # Architecture & configuration guides
│
├── ecs-bedrock-agentcore-runtime-solution/ # AgentCore Runtime + Strands on ECS
│   ├── strands-agents/                     # Strands-based agents (AWS API, Cost, WA Security)
│   ├── deployment-scripts/                 # CloudFormation, deploy scripts, agent registration
│   ├── ecs-backend/                        # FastAPI backend with AgentCore integration
│   ├── frontend/                           # Web interface with prompt templates
│   └── docs/                               # Architecture & configuration guides
│
├── ecs-bedrock-agentcore-longrun-solution/ # AgentCore long-running task orchestrator
│   ├── kiro-agentcore-runtime/             # Custom AgentCore runtime wrapper
│   ├── deployment-scripts/                 # CloudFormation template and deploy script
│   ├── ecs-backend/                        # FastAPI orchestrator with WebSocket
│   ├── frontend-react/                     # CloudScape chat UI
│   └── docs/                               # Architecture documentation
│
└── mcp-servers/                            # MCP server forks with IAM role support
    ├── aws-api-mcp-server-with-iamrole-support/
    └── well-architected-security-mcp-server-with-iamrole-support/
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
