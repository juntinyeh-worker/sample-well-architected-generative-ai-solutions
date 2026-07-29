# TODO: Multi-Role Extension

**Owner:** SpongeBob  
**Branch:** `feature/strands-agentcore-runtime-multirole-extend`  
**Priority:** P0 = must do, P1 = should do, P2 = nice to have

---

## P0 — Complete the Integration

- [ ] **Update `requirements.txt`** — add `requests>=2.28.0` (needed by `plx_support_assistant_client/auth.py`)
- [ ] **Update `Dockerfile`** — change base to `python:3.12-slim` OR fix AL2023 python install for ARM. Add `COPY shared/plx_support_assistant_client ./plx_support_assistant_client` and `COPY steering/ ./steering/`
- [ ] **Add `SUPPORT_API_REGION=us-east-1`** to Dockerfile ENV
- [ ] **Test container builds locally** — `docker build -t strands-agentcore-support:latest .`
- [ ] **Fix model ID** — ensure `DEFAULT_MODEL_ID` uses inference profile format: `us.anthropic.claude-opus-4-6-v1` (not bare model ID which fails with `ValidationException`)

---

## P0 — Multi-Role Steering Packs

- [ ] **Keep `wa-security-workflow.md`** as an alternate role (already exists)
- [ ] **Add role switcher** — modify `main.py` to accept `steering` field in payload for per-request role selection:
  ```python
  steering_pack = payload.get("steering", "")
  if steering_pack:
      os.environ["STEERING_PATH"] = f"/app/steering/{steering_pack}"
  ```
- [ ] **Create `steering/wa-security/` directory** — move `wa-security-workflow.md` → `steering/wa-security/flow.md` + add `product.md`
- [ ] **Create `steering/cost-optimization/`** — new role for cost analysis (template in GUIDE-001)
- [ ] **Test steering swap** — invoke with `{"input": "...", "steering": "support-investigation"}` vs `{"steering": "wa-security"}`

---

## P1 — Multi-Account (CODA) Support

- [ ] **Add `account_id` parameter** to `start_support_interaction` tool
- [ ] **Implement credential brokering** — invoke coda-broker Lambda for multi-account STS sessions
- [ ] **Per-interaction credential store** — store STS triplet per `interactionId` (required: API ties ownership to exact session)
- [ ] **Add `CODA_BROKER_FUNCTION_NAME` env var** support
- [ ] **Reference:** See `sup-beta/services/mcp-server/session_store.py` for the production pattern

---

## P1 — Production Hardening

- [ ] **Add error retry** — `support_tools.py` currently catches exceptions and returns error strings; add bounded retry for 429/503
- [ ] **Add interaction timeout** — if `get_interaction_status` returns IN_PROGRESS for >5 min, auto-resolve and report
- [ ] **Wire logging** — add optional verbose logging of Support API request/response bodies (gated by `LOG_LEVEL=DEBUG`)
- [ ] **Sanitize PII** — `plx_support_assistant_client/text_sanitizer.py` is available; ensure it's called before `start_interaction`

---

## P1 — Testing

- [ ] **Create `tests/` directory** with pytest structure
- [ ] **Unit tests for `support_tools.py`** — mock `SupportInteractionsClient`, verify all 8 tools (see QA-001 for 14 test cases)
- [ ] **Unit tests for steering loader** — local + S3 + empty (8 test cases in QA-001)
- [ ] **Integration test script** — invoke deployed Lambda, validate response structure
- [ ] **Target: 90% coverage**

---

## P2 — New Roles to Build

- [ ] **Incident Response** — `steering/incident-response/flow.md` (Detect → Contain → Investigate → Recover)
- [ ] **Compliance Checker** — `steering/compliance/flow.md` (AWS Config + SecurityHub data → report)
- [ ] **Cost Optimization** — `steering/cost-optimization/flow.md` (Cost Explorer + utilization metrics → savings)

---

## P2 — Infrastructure

- [ ] **Create dedicated CodeBuild project** — `sandbox-agent-bridge-build` (don't reuse existing projects)
- [ ] **Create CloudFormation template** — API Gateway + Lambda + IAM (see `sup-beta/docs/SPEC-002-sidecar-stack-cfn.md`)
- [ ] **Function URL alternative** — if Org SCP blocks Function URLs, use API Gateway in us-west-2 (needs `apigateway:*` in us-west-2)
- [ ] **CI/CD** — trigger CodeBuild on git push to this branch

---

## Reference Commands

```bash
# Build locally
cd ecs-bedrock-agentcore-longrun-solution/strands-agentcore-runtime
cp -r shared/plx_support_assistant_client .
docker build -t strands-agentcore-support:latest .

# Push to ECR
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR=256358067059.dkr.ecr.us-west-2.amazonaws.com/sandbox-agent-bridge-support
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $ECR
docker tag strands-agentcore-support:latest $ECR:latest
docker push $ECR:latest

# Update runtime
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id support_investigation_agent-4GGI332sXD \
  --role-arn arn:aws:iam::256358067059:role/coav2-bedrock-agentcore-runtime-role \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"'"$ECR"':latest"}}' \
  --region us-west-2

# Test
aws lambda invoke --function-name sandbox-agent-bridge-poc --region us-west-2 \
  --cli-binary-format raw-in-base64-out \
  --payload '{"requestContext":{"http":{"method":"POST","path":"/invoke"}},"body":"{\"input\":\"List my S3 buckets\"}"}' \
  /tmp/out.json && python3 -c "import json;d=json.load(open('/tmp/out.json'));print(json.loads(d['body'])['response'])"
```

---

## Key Contacts

- **bobyeh1624** — project owner, decides architecture direction
- **PatrickStar** — built the POC, wrote all docs/specs, deployed the sidecar
- **SpongeBob** — you, continuing development on this branch
