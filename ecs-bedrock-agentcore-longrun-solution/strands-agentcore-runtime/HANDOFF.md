# Handoff: Strands AgentCore Runtime — Multi-Role Extension

**From:** PatrickStar  
**To:** SpongeBob  
**Date:** 2026-07-29  
**Branch:** `feature/strands-agentcore-runtime-multirole-extend`  
**Base:** `feature/strands-agentcore-runtime` (4 commits by SpongeBob/kiro-agent)

---

## What Was Done

PatrickStar extended the strands-agentcore-runtime with Support Interactions API integration as a POC for the `sup-beta` project. The core agent pattern (BedrockAgentCoreApp + per-request agent creation + steering loader) was preserved exactly. New capabilities were added on top.

### Files Added

| File | Purpose |
|------|---------|
| `support_tools.py` | 8 `@tool` functions wrapping AWS Support Interactions API + Cases API |
| `shared/plx_support_assistant_client/` | SigV4 client library for `assistant.support.{region}.amazonaws.com` (not yet in boto3 SDK) |
| `steering/support-investigation/product.md` | Agent identity definition for support investigation role |
| `steering/support-investigation/flow.md` | 4-phase workflow: Understand → Inspect → Escalate → Report |

### Files Modified

| File | Change |
|------|--------|
| `aws_api_agent.py` | Added imports for 8 support tools + registered them in `create_supervisor_agent()` tools list. Updated `base_prompt` to describe all available tools. Changed `DEMO_READ_ONLY` default to `true`. Model ID default now uses `us.` prefix inference profile format. |

### Files NOT Modified

| File | Notes |
|------|-------|
| `main.py` | Identical — async task pattern preserved |
| `steering.py` | Identical — .md loader unchanged |
| `src/` (MCP server) | Not touched — still present, optional |
| `Dockerfile` | Not modified in this branch (see TODO) |
| `requirements.txt` | Not modified in this branch (see TODO) |

---

## Architecture Context

This work feeds into the **sup-beta** project (Support Assistant Beta Kit). The sup-beta team wants to:

1. Deploy this agent as a **standalone sidecar stack** (separate CloudFormation, not touching sup-beta)
2. Use it to bridge between clients and the AWS Support Interactions API
3. Swap steering files to reuse the same agent for multiple roles (security review, cost optimization, incident response, etc.)

### Key Design Decision (ADR-001)

The agent is deployed as a **completely separate stack** from sup-beta. No cross-stack references. Both stacks independently call the Support Interactions API. See `sup-beta/docs/ADR-001-sidecar-agent-stack.md`.

---

## How It Works

```
Client → Lambda (agent-bridge) → AgentCore Runtime → Strands Agent
                                                         ↓
                                          ┌──────────────────────────────┐
                                          │ Tools:                       │
                                          │  • call_aws (CLI)            │
                                          │  • call_boto3 (SDK)          │
                                          │  • think (reasoning)         │
                                          │  • start_support_interaction │
                                          │  • get_interaction_status    │
                                          │  • update_support_interaction│
                                          │  • resolve_support_interaction│
                                          │  • list_support_interactions │
                                          │  • list_interaction_entries  │
                                          │  • create_support_case       │
                                          │  • describe_support_cases    │
                                          └──────────────────────────────┘
                                                         ↓
                                          Bedrock (Claude) + AWS APIs + Support API
```

### Steering-Driven Multi-Role

The agent loads `.md` steering files on every request. The steering defines:
- **Who** the agent is (product.md)
- **What** workflow it follows (flow.md)
- **What** it cannot do (constraints)

Same container, same tools, different behavior — just by pointing `STEERING_PATH` or `STEERING_S3_URI` to a different directory.

---

## Deployed & Validated (in account 256358067059, us-west-2)

| Resource | Value | Status |
|----------|-------|--------|
| ECR Repo | `sandbox-agent-bridge-support` | ✅ Has image |
| AgentCore Runtime | `support_investigation_agent-4GGI332sXD` | ✅ READY |
| Lambda | `sandbox-agent-bridge-poc` | ✅ Working |
| IAM Role (Lambda) | `sandbox-agent-bridge-role-poc` | ✅ |
| IAM Policy (Runtime) | `support:*` on `coav2-bedrock-agentcore-runtime-role` | ✅ Added |
| Model ID | `us.anthropic.claude-opus-4-6-v1` | ✅ Working |

### Test Command
```bash
aws lambda invoke --function-name sandbox-agent-bridge-poc --region us-west-2 \
  --cli-binary-format raw-in-base64-out \
  --payload '{"requestContext":{"http":{"method":"POST","path":"/invoke"}},"body":"{\"input\":\"Check my EC2 instance health\"}"}' \
  /tmp/out.json && python3 -c "import json;d=json.load(open('/tmp/out.json'));print(json.loads(d['body'])['response'])"
```

---

## Support Interactions API — Key Facts

- **Endpoint:** `https://assistant.support.{region}.amazonaws.com`
- **Not in boto3 SDK yet** — uses `plx_support_assistant_client` (SigV4 shim)
- **Operations:** start_interaction, get_interaction, update_interaction, resolve_interaction, list_interactions, list_interaction_entries
- **Auth:** SigV4 with service name `"support"`
- **Credential constraint:** Interaction ownership tied to EXACT STS session that created it (critical for multi-account)
- **Region:** Usually `us-east-1` regardless of deployment region

---

## Related Repos & Docs

| Location | Content |
|----------|---------|
| `juntinyeh-worker/sup-beta` branch `poc/agent-integration-noauth` | Full sidecar implementation + docs |
| `sup-beta/docs/ADR-001-sidecar-agent-stack.md` | Architecture decision |
| `sup-beta/docs/SPEC-001-agent-detail-specification.md` | Full agent spec |
| `sup-beta/docs/SPEC-002-sidecar-stack-cfn.md` | CloudFormation spec |
| `sup-beta/docs/GUIDE-001-extending-agent-roles.md` | How to add new roles |
| `sup-beta/docs/QA-001-test-plan.md` | 38 unit + 19 integration tests |
| `agent-memory/2026-07-27-sidecar-agent-stack-planning.md` | Session record |
| CloudFront diagram | https://dp4h2crcz27h7.cloudfront.net/docs/sup-beta-architecture-diagrams.html |

---

## Known Issues & Limitations

1. **Function URL blocked by Org SCP** — can't expose Lambda publicly via Function URL. Workaround: direct `aws lambda invoke` or need APIGW in us-west-2
2. **Support Cases API needs Business plan** — `describe_cases`, `create_case` return `SubscriptionRequiredException` without Business/Enterprise support
3. **Single-account only** — multi-account (CODA) credential brokering not implemented in `support_tools.py` yet (pattern exists in sup-beta's MCP server)
4. **ARM build** — CodeBuild project is ARM; Dockerfile uses `python:3.12-slim` which is multi-arch (works fine)
5. **No MCP server in support role** — the `src/` embedded MCP server is present but not used by support tools (they call the API directly via the SigV4 client)
