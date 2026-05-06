# WA Security Quick Scan

A minimal, non-interactive AWS Well-Architected Security assessment that works on any AWS account — including legacy accounts without GuardDuty, Security Hub, or Config enabled.

## What It Does

Runs programmatic security checks using raw AWS resource data (IAM, Security Groups, S3, EBS, CloudTrail, VPC Flow Logs) and produces:

1. **Markdown summary** — text report with findings by severity
2. **HTML visual report** — self-contained, styled report you can open in any browser

## Quick Start

```bash
# Ensure AWS credentials are configured
aws sts get-caller-identity

# Run the scan (defaults to us-east-1)
python3 wa-security/scripts/security-scan.py

# Scan a different region
python3 wa-security/scripts/security-scan.py --region ap-southeast-1

# Custom output directory
python3 wa-security/scripts/security-scan.py --output-dir ./my-reports
```

## Prerequisites

- Python 3.9+
- AWS CLI configured with read-only credentials
- No pip packages required (stdlib only)

## Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "sts:GetCallerIdentity",
      "iam:GetAccountSummary",
      "iam:GetAccountPasswordPolicy",
      "iam:ListUsers",
      "iam:ListAccessKeys",
      "iam:ListVirtualMFADevices",
      "cloudtrail:DescribeTrails",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeVolumes",
      "ec2:DescribeFlowLogs",
      "s3:ListAllMyBuckets",
      "s3:GetBucketEncryption",
      "s3:GetPublicAccessBlock",
      "s3:GetBucketPolicyStatus",
      "guardduty:ListDetectors",
      "securityhub:DescribeHub",
      "config:DescribeConfigurationRecorders"
    ],
    "Resource": "*"
  }]
}
```

## Output

Reports are written to `wa-security/reports/` (default):

| File | Description |
|------|-------------|
| `security-scan-summary.md` | Markdown findings report |
| `security-scan-report.html` | Visual HTML report (open in browser) |

## How It Handles Legacy Accounts

The scanner uses a two-tier approach:

- **Raw data checks** — Always work. Examines actual IAM, SG, S3, EBS, and network configurations.
- **Service status checks** — Reports whether GuardDuty/Security Hub/Config are enabled as recommendations.

Findings are tagged `[raw]` or `[service]` so you know which are based on hard evidence vs. service-enablement suggestions.
