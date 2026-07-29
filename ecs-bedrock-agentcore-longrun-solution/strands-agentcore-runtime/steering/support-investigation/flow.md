# Support Investigation Workflow

## Phase 1: UNDERSTAND

### 1.1 Parse User Request
- Identify the affected AWS service(s) and specific resource(s)
- Classify the symptom: connectivity | performance | error | permissions | configuration
- Extract any timestamps, error codes, or resource identifiers mentioned
- If the request is vague, ask ONE clarifying question before proceeding

### 1.2 Plan Investigation
Use `think` to plan which resources to inspect and in what order.
Prioritize checks that are most likely to reveal the issue based on the symptom type.

---

## Phase 2: INSPECT (Evidence Gathering)

### 2.1 Resource State
Use `call_boto3` to check the current state of affected resources:
- EC2: `describe_instances`, `describe_instance_status`
- RDS: `describe_db_instances`, `describe_events`
- ECS: `describe_services`, `describe_tasks`, `list_tasks`
- Lambda: `get_function_configuration`, `list_event_source_mappings`
- S3: `get_bucket_policy`, `get_public_access_block`
- ALB/NLB: `describe_target_health`, `describe_load_balancers`

### 2.2 Network & Security (if connectivity issue)
- Security groups: `describe_security_groups` (check inbound/outbound rules)
- NACLs: `describe_network_acls`
- Route tables: `describe_route_tables`
- VPC endpoints: `describe_vpc_endpoints`

### 2.3 Metrics & Logs (if performance/error issue)
- CloudWatch: `get_metric_data` for relevant metrics (CPU, memory, errors, latency)
- Recent events: `describe_events` or CloudTrail `lookup_events` (last 1 hour)

### 2.4 Summarize Evidence
After gathering, use `think` to:
- List all findings
- Identify anomalies or misconfigurations
- Determine if you can diagnose the issue yourself

---

## Phase 3: DIAGNOSE OR ESCALATE

### Path A: Self-Diagnosis (if root cause is clear)
If the evidence clearly points to a misconfiguration or known pattern:
- Report the root cause directly
- Skip to Phase 4: REPORT

### Path B: Escalate to Support API (if unclear)
If self-diagnosis is insufficient:

1. **Compose message** for `start_support_interaction`:
   - Start with the symptom (1 sentence)
   - Include resource identifiers
   - Include ALL evidence gathered (summarized, not raw JSON)
   - Include timestamps
   - Include what you've already checked

2. **Start interaction** and note the `interactionId`

3. **Poll** with `get_interaction_status` (wait 10+ seconds between calls):
   - If `IN_PROGRESS` → wait and poll again
   - If `AWAITING_INPUT` → read the follow-up question, answer from evidence gathered in Phase 2 using `update_support_interaction`, then continue polling
   - If `COMPLETED` → extract findings from `result.details`
   - If `FAILED` → report failure and suggest `create_support_case`

4. **Max polls**: 12 attempts (≈2 minutes). If still IN_PROGRESS, report partial status.

### Path C: Create Support Case (last resort)
If the Support API cannot resolve the issue:
1. Compile all evidence into a comprehensive description
2. Call `create_support_case` with full context
3. Report case ID to user

---

## Phase 4: REPORT

Provide the user with a structured response:

```
## Summary
[1-2 sentence executive summary of the finding]

## Root Cause
[What is causing the issue — be specific]

## Evidence
[Key data points that support the diagnosis]

## Recommendations
1. [Specific action to resolve]
2. [Additional steps if needed]
3. [Preventive measure for the future]

## Tracking
- Support Interaction ID: [if escalated]
- Support Case ID: [if created]
```

---

## Execution Rules

1. **Evidence first**: ALWAYS inspect resources before calling Support API
2. **Rich context**: Include maximum evidence in the initial support message
3. **Throttle polls**: Wait 10+ seconds between `get_interaction_status` calls
4. **Auto-answer**: If Support asks a question you can answer from Phase 2 evidence, answer it — don't ask the user
5. **Read-only**: All inspection uses Describe*/Get*/List* operations only
6. **Be concise**: Final report should be actionable, not a data dump
7. **Fail gracefully**: If any tool call fails, log the error and continue with available information
