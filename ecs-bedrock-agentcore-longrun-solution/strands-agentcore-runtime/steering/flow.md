# WA Review Flow

## Review Process

When a user requests a Well-Architected review, follow this flow:

### Step 1: Scope Discovery
- Ask which pillars to focus on (or review all)
- Identify target account/region
- Determine workload scope (specific services, tags, or all resources)

### Step 2: Automated Checks (per pillar)
Execute checks in order:
1. **Security** — IAM, encryption, network, logging
2. **Reliability** — Multi-AZ, backups, health checks
3. **Performance** — Right-sizing, scaling, caching
4. **Cost Optimization** — Unused resources, reserved capacity, right-sizing
5. **Operational Excellence** — Monitoring, tagging, automation
6. **Sustainability** — Resource efficiency

### Step 3: Evidence Collection
For each check:
- Use `call_boto3` or `call_aws` to gather evidence
- Record specific resource ARNs and configurations
- Note deviations from best practices

### Step 4: Findings Report
Produce a summary with:
- Total checks run
- Pass/Fail/Warning counts by pillar
- Top findings by severity
- Prioritized recommendations

### Step 5: Deep Dive (on request)
If user asks for detail on any finding:
- Show exact resource configurations
- Explain the risk
- Provide step-by-step remediation
