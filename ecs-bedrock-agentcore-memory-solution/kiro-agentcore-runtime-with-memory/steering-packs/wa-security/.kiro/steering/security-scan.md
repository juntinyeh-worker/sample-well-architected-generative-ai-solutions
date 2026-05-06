---
inclusion: auto
---

# WA Security Quick Scan — Steering

## Purpose

This steering file guides Kiro to run a non-interactive AWS security assessment using raw resource data. It works on any AWS account, including legacy accounts without managed security services enabled.

## Workflow

When the user asks to run a security scan or security assessment:

1. **Assume role if target account provided**: If the prompt includes a target account/role, run:
   ```bash
   CREDS=$(aws sts assume-role --role-arn <ROLE_ARN> --role-session-name <SESSION> --external-id <EXTERNAL_ID> --output json)
   export AWS_ACCESS_KEY_ID=$(echo $CREDS | python3 -c "import sys,json;print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
   export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | python3 -c "import sys,json;print(json.load(sys.stdin)['Credentials']['SecretAccessKey'])")
   export AWS_SESSION_TOKEN=$(echo $CREDS | python3 -c "import sys,json;print(json.load(sys.stdin)['Credentials']['SessionToken'])")
   ```
2. **Verify credentials**: Run `aws sts get-caller-identity` to confirm access
3. **Execute the scanner**: Run `python3 wa-security/scripts/security-scan.py --region <REGION>`
4. **Present results**: Show the summary findings and point to the HTML report

## Key Principles

- **No human interaction required** — the scan runs end-to-end automatically
- **Raw data first** — assess security from actual resource configurations (IAM keys, security groups, S3 policies, EBS encryption) before checking service enablement
- **Context-aware** — only flag issues for resources that actually exist in the account
- **Legacy-friendly** — works without GuardDuty, Security Hub, Config, or Inspector

## Security Checks Performed

### Raw Data Checks (always work)
| Check | Severity | Data Source |
|-------|----------|-------------|
| Root account access keys | CRITICAL | IAM |
| SSH/RDP open to 0.0.0.0/0 | CRITICAL | Security Groups |
| CloudTrail not configured | CRITICAL | CloudTrail |
| Access keys older than 90 days | HIGH | IAM |
| IAM users without MFA | HIGH | IAM |
| S3 buckets potentially public | HIGH | S3 |
| Non-standard ports open to internet | HIGH | Security Groups |
| S3 buckets without encryption | MEDIUM | S3 |
| Unencrypted EBS volumes | MEDIUM | EBS |
| No VPC Flow Logs | MEDIUM | VPC |
| No IAM password policy | MEDIUM | IAM |
| CloudTrail not multi-region | MEDIUM | CloudTrail |
| CloudTrail log validation disabled | LOW | CloudTrail |

### Service Status Checks (recommendations)
| Check | Severity |
|-------|----------|
| GuardDuty not enabled | HIGH |
| Security Hub not enabled | MEDIUM |
| AWS Config not enabled | MEDIUM |

## Output Files

- `wa-security/reports/security-scan-summary.md` — Markdown text report
- `wa-security/reports/security-scan-report.html` — Visual HTML report

## Usage Examples

```bash
# Default scan (us-east-1)
python3 wa-security/scripts/security-scan.py

# Specific region
python3 wa-security/scripts/security-scan.py --region eu-west-1

# Custom output
python3 wa-security/scripts/security-scan.py --output-dir /tmp/scan-results
```

## Final Step: Upload Reports to S3

IMPORTANT: After the scan completes, revert to sandbox credentials before uploading:
```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

Upload reports and generate presigned URLs:
```bash
BUCKET="sandbox-longrun-0426-logs-256358067059"
DATE=$(date -u +%Y-%m-%d)

aws s3 cp wa-security/reports/security-scan-report.html "s3://$BUCKET/reports/$DATE/security-scan-report.html" --region us-west-2
aws s3 cp wa-security/reports/security-scan-summary.md "s3://$BUCKET/reports/$DATE/security-scan-summary.md" --region us-west-2

HTML_URL=$(aws s3 presign "s3://$BUCKET/reports/$DATE/security-scan-report.html" --expires-in 604800 --region us-west-2)
MD_URL=$(aws s3 presign "s3://$BUCKET/reports/$DATE/security-scan-summary.md" --expires-in 604800 --region us-west-2)
```

Include in your final output:
```
📊 **Reports:**
- [Security Report (HTML)]($HTML_URL)
- [Security Report (Markdown)]($MD_URL)
```

Do NOT skip the upload step. Execute it after the scan completes.
