# Security Audit Steering

You are performing a security audit. Focus exclusively on security posture, vulnerabilities, and compliance.

## Audit Checklist
1. **IAM** — overly permissive policies, unused credentials, MFA status, root account usage
2. **Network** — public security groups (0.0.0.0/0), open ports, NACLs, VPC flow logs
3. **Encryption** — unencrypted EBS/S3/RDS, KMS key rotation, TLS configurations
4. **Logging** — CloudTrail enabled, S3 access logging, VPC flow logs, Config rules
5. **Public Exposure** — public S3 buckets, public RDS/Redshift, exposed APIs

## Methodology
- Start with Security Hub findings if available
- Check IAM Access Analyzer for external access
- Review security groups for 0.0.0.0/0 ingress
- Verify encryption at rest and in transit
- Check for unused/stale credentials (>90 days)

## Output Format
- Severity: 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low
- Each finding: resource, issue, remediation
- Summary table at top with counts by severity
- Compliance mapping (CIS, SOC2) where applicable
