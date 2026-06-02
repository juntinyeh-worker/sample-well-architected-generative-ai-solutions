# Autonomous Security-Only WAFR Workflow

**Mode**: Fully autonomous — zero human interaction after invocation.
**Scope**: Security pillar only (General AWS Well-Architected Framework).
**Output**: Markdown report with prioritized findings and remediation recommendations.

---

## Phase 1: BOOTSTRAP

### 1.1 Detect AWS CLI

```bash
aws --version 2>/dev/null
```

- If found: proceed.
- If not found: HALT with error message explaining AWS CLI is required.

### 1.2 Validate Credentials

```bash
aws sts get-caller-identity
```

- If valid: extract role/user ARN, proceed to permission check.
- If invalid: HALT with error message.

### 1.3 Validate Permission Boundary

Extract role name from ARN and check attached policies:

```bash
aws iam list-attached-role-policies --role-name <role>
```

**PASS conditions** (any of):
- ReadOnlyAccess, ViewOnlyAccess, SecurityAudit, ReadOnly* policies

**FAIL conditions** (any of):
- AdministratorAccess, *FullAccess, any write/modify/delete policies

- If PASS: log credential info, proceed.
- If FAIL: HALT. Display: "Credential exceeds read-only boundary. Provide a ReadOnly credential."

### 1.4 Log Environment

```
[BOOTSTRAP] Environment:
• AWS CLI: [version]
• Identity: [ARN]
• Permission Boundary: ✅ Compliant
• Mode: Autonomous (no interaction)
```

---

## Phase 2: DISCOVER

### 2.1 Workload Discovery

Auto-discover infrastructure in the account:

```bash
# Core services inventory
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Cidr:CidrBlock}' --output json
aws ec2 describe-instances --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name}' --output json
aws lambda list-functions --query 'Functions[].{Name:FunctionName,Runtime:Runtime}' --output json
aws rds describe-db-instances --query 'DBInstances[].{Id:DBInstanceIdentifier,Engine:Engine}' --output json
aws s3api list-buckets --query 'Buckets[].Name' --output json
aws ecs list-clusters --output json
aws eks list-clusters --output json
```

Record workload summary: services detected, region, account ID.

### 2.2 Security Assessment (SEC1–SEC7)

Execute ALL checks programmatically. For each security area, run the AWS CLI commands, classify the finding, and move on.

#### SEC1: Identity and Access Management

```bash
# Check for root account MFA
aws iam get-account-summary --query 'SummaryMap.AccountMFAEnabled'

# Find users without MFA
aws iam generate-credential-report
aws iam get-credential-report --output text --query 'Content' | base64 -d | grep -v "^<" | awk -F',' '$4=="false" && $1!="<root_account>" {print $1}'

# Find users with access keys older than 90 days
aws iam get-credential-report --output text --query 'Content' | base64 -d | awk -F',' '$9!="N/A" && $9!="access_key_1_last_rotated" {print $1, $9}'

# Find overly permissive policies (wildcard actions)
aws iam list-policies --scope Local --query 'Policies[].Arn' --output text | xargs -I{} aws iam get-policy-version --policy-arn {} --version-id $(aws iam get-policy --policy-arn {} --query 'Policy.DefaultVersionId' --output text) --query 'PolicyVersion.Document'

# Check for IAM Access Analyzer
aws accessanalyzer list-analyzers --query 'analyzers[].{name:name,status:status}'
```

**Classify**: HRI if root has no MFA, users lack MFA, or wildcard policies exist. MRI if key rotation overdue.

#### SEC2: Detective Controls

```bash
# GuardDuty status
aws guardduty list-detectors --output json
# For each detector:
aws guardduty get-detector --detector-id <id> --query '{Status:Status,FindingPublishingFrequency:FindingPublishingFrequency}'

# Security Hub status
aws securityhub describe-hub 2>/dev/null

# CloudTrail status
aws cloudtrail describe-trails --query 'trailList[].{Name:Name,IsMultiRegion:IsMultiRegionTrail,IsLogging:HasCustomEventSelectors}'
aws cloudtrail get-trail-status --name <trail> --query '{IsLogging:IsLogging}'

# AWS Config status
aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[].{name:name,recording:recordingGroup.allSupported}'
aws configservice describe-configuration-recorder-status --query 'ConfigurationRecordersStatus[].{name:name,recording:recording}'

# Inspector status
aws inspector2 batch-get-account-status --query 'accounts[].{status:state.status}'
```

**Classify**: HRI if CloudTrail disabled or GuardDuty not enabled. MRI if Security Hub/Config/Inspector not enabled.

#### SEC3: Infrastructure Protection

```bash
# Security groups with 0.0.0.0/0 ingress on sensitive ports
aws ec2 describe-security-groups --query 'SecurityGroups[].{Id:GroupId,Name:GroupName,Rules:IpPermissions[?contains(IpRanges[].CidrIp,`0.0.0.0/0`)]}' --output json

# Public subnets
aws ec2 describe-route-tables --query 'RouteTables[].{SubnetAssociations:Associations[].SubnetId,Routes:Routes[?GatewayId!=null && starts_with(GatewayId,`igw-`)]}'

# WAF WebACLs
aws wafv2 list-web-acls --scope REGIONAL --query 'WebACLs[].{Name:Name,Id:Id}'

# Network Firewall
aws network-firewall list-firewalls --query 'Firewalls[].FirewallName'

# VPC Flow Logs
aws ec2 describe-flow-logs --query 'FlowLogs[].{Id:FlowLogId,Status:FlowLogStatus,VpcId:ResourceId}'
```

**Classify**: HRI if security groups allow 0.0.0.0/0 on ports 22/3389/3306/5432. MRI if no WAF or no flow logs.

#### SEC4: Data Protection in Transit

```bash
# Load balancer listeners using HTTP (not HTTPS)
aws elbv2 describe-listeners --query 'Listeners[?Protocol==`HTTP`].{LB:LoadBalancerArn,Port:Port}'

# CloudFront distributions without HTTPS redirect
aws cloudfront list-distributions --query 'DistributionList.Items[].{Id:Id,ViewerProtocol:DefaultCacheBehavior.ViewerProtocolPolicy}'

# API Gateway stages without client certificates
aws apigateway get-rest-apis --query 'items[].{id:id,name:name}' --output json
```

**Classify**: HRI if load balancers serving HTTP on public endpoints. MRI if no HTTPS enforcement on CloudFront/API Gateway.

#### SEC5: Data Protection at Rest

```bash
# S3 buckets without encryption
aws s3api list-buckets --query 'Buckets[].Name' --output text | xargs -I{} sh -c 'echo "{}:" && aws s3api get-bucket-encryption --bucket {} 2>&1'

# Unencrypted EBS volumes
aws ec2 describe-volumes --query 'Volumes[?Encrypted==`false`].{Id:VolumeId,Size:Size,State:State}'

# Unencrypted RDS instances
aws rds describe-db-instances --query 'DBInstances[?StorageEncrypted==`false`].{Id:DBInstanceIdentifier,Engine:Engine}'

# KMS key rotation status
aws kms list-keys --query 'Keys[].KeyId' --output text | xargs -I{} aws kms get-key-rotation-status --key-id {}

# Secrets Manager usage
aws secretsmanager list-secrets --query 'SecretList[].{Name:Name,LastRotated:LastRotatedDate}'
```

**Classify**: HRI if RDS or EBS unencrypted. MRI if S3 buckets lack encryption or KMS keys not rotated.

#### SEC6: Incident Response

```bash
# Check for AWS Backup plans
aws backup list-backup-plans --query 'BackupPlansList[].{Id:BackupPlanId,Name:BackupPlanName}'

# EventBridge rules for security events
aws events list-rules --query 'Rules[?starts_with(Name,`securityhub`) || contains(Name,`security`) || contains(Name,`guardduty`)].{Name:Name,State:State}'

# SNS topics for security alerting
aws sns list-topics --query 'Topics[].TopicArn' --output text | grep -i security

# SSM automation documents for incident response
aws ssm list-documents --document-filter-list key=Owner,value=Self --query 'DocumentIdentifiers[?contains(Name,`incident`) || contains(Name,`remediat`)].Name'
```

**Classify**: HRI if no backup plans exist. MRI if no automated alerting or incident response automation.

#### SEC7: Application Security

```bash
# ECR image scan findings
aws ecr describe-repositories --query 'repositories[].{Name:repositoryName,ScanOnPush:imageScanningConfiguration.scanOnPush}'

# Inspector findings summary (application vulnerabilities)
aws inspector2 list-finding-aggregations --aggregation-type REPOSITORY --query 'responses[].{repo:repository.name,critical:severityCounts.critical,high:severityCounts.high}'

# CodeBuild projects (check for security scanning)
aws codebuild list-projects --query 'projects'
```

**Classify**: HRI if ECR scan-on-push disabled with critical vulnerabilities. MRI if no application security scanning in CI/CD.

### 2.3 Risk Classification

After all checks complete, consolidate into:

- **HRI (High Risk Issues)**: Immediate action required — active security gaps that could be exploited.
- **MRI (Medium Risk Issues)**: Should be addressed — defense-in-depth gaps or missing best practices.

Sort by severity, then by blast radius.

---

## Phase 3: REPORT

Generate a single markdown report at `wafr-reports/security-assessment-[YYYY-MM-DD].md`:

```markdown
# AWS Security Assessment Report

**Date**: [YYYY-MM-DD]
**Account**: [Account ID]
**Region**: [Region]
**Identity**: [Role/User ARN]
**Mode**: Autonomous Security-Only Assessment

## Executive Summary

- **High Risk Issues (HRI)**: [count]
- **Medium Risk Issues (MRI)**: [count]
- **Security Services Enabled**: [X/7] (CloudTrail, GuardDuty, Security Hub, Config, Inspector, Macie, Access Analyzer)

## Critical Findings (HRI)

### [Finding Title]
- **Area**: SEC[N] - [Area Name]
- **Impact**: [Description of business/security impact]
- **Evidence**: [Specific AWS CLI output proving the finding]
- **Remediation**: [Specific steps to fix, with AWS CLI commands]
- **Priority**: Immediate

[Repeat for each HRI]

## Medium Findings (MRI)

### [Finding Title]
- **Area**: SEC[N] - [Area Name]
- **Impact**: [Description]
- **Evidence**: [Specific data]
- **Remediation**: [Steps]
- **Priority**: Short-term (30 days)

[Repeat for each MRI]

## Security Services Status

| Service | Status | Recommendation |
|---------|--------|---------------|
| CloudTrail | ✅/❌ | [action if needed] |
| GuardDuty | ✅/❌ | [action if needed] |
| Security Hub | ✅/❌ | [action if needed] |
| AWS Config | ✅/❌ | [action if needed] |
| Inspector | ✅/❌ | [action if needed] |
| Macie | ✅/❌ | [action if needed] |
| IAM Access Analyzer | ✅/❌ | [action if needed] |

## Remediation Roadmap

### Week 1 (Critical)
1. [HRI remediation steps]

### Weeks 2-4 (Important)
1. [MRI remediation steps]

### Ongoing
1. [Operational improvements]
```

---

## Error Handling

- If an AWS API call fails (access denied, service not available in region): log the error, skip that check, note it as "Unable to assess" in the report.
- If >50% of checks fail: append a warning to the report that assessment coverage is limited due to permission constraints.
- Never halt the entire workflow for a single API failure — assess what you can.

---

## Execution Rules

1. **Zero interaction**: No prompts, no confirmations, no "would you like to continue?"
2. **Fail-forward**: Skip failed checks, don't stop the workflow.
3. **Evidence-based**: Every finding must include the specific AWS CLI output that proves it.
4. **Actionable**: Every finding must include specific remediation commands.
5. **Single output**: One markdown file in `wafr-reports/`.
6. **Idempotent**: Can be re-run any time without side effects (read-only operations only).
