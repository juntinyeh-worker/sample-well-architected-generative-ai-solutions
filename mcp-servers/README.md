# MCP Servers

Forked MCP (Model Context Protocol) server implementations with cross-account IAM AssumeRole support, used by the ECS Bedrock solutions in this repository.

## Servers

| Server | Description |
|--------|-------------|
| [aws-api-mcp-server-with-iamrole-support](aws-api-mcp-server-with-iamrole-support/) | AWS API MCP server enabling AI assistants to execute AWS CLI commands with cross-account IAM role support |
| [well-architected-security-mcp-server-with-iamrole-support](well-architected-security-mcp-server-with-iamrole-support/) | Well-Architected security assessment MCP server with cross-account IAM role support |

## Overview

These are forks of the upstream [awslabs MCP servers](https://github.com/awslabs/mcp) with added support for `sts:AssumeRole` cross-account access. They are consumed by the Bedrock Agent and AgentCore Runtime solutions as tool providers.

### aws-api-mcp-server-with-iamrole-support

Provides `call_aws` and `suggest_aws_commands` tools for executing validated AWS CLI commands. See the [full README](aws-api-mcp-server-with-iamrole-support/README.md) for installation, configuration, and security details.

### well-architected-security-mcp-server-with-iamrole-support

Provides security assessment tools aligned with the AWS Well-Architected Framework Security pillar — network encryption checks, storage encryption analysis, and security service status.

## License

MIT-0 — See [LICENSE](../LICENSE).
