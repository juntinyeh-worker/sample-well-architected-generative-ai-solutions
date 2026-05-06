---
inclusion: auto
---

# Report Upload Instructions

After generating any report files (.html, .md, .pdf), you MUST switch back to the sandbox (local) identity to upload them.

## Identity Switching

The scan runs with ASSUMED ROLE credentials (target account). Before uploading reports, you must UNSET those credentials to revert to the AgentCore Runtime's native IAM role (sandbox account):

```bash
# IMPORTANT: Clear assumed role credentials to revert to sandbox identity
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# Verify you're back on the sandbox account
aws sts get-caller-identity
```

## Upload Procedure

After reverting to sandbox identity, for EACH generated report file:

```bash
BUCKET="sandbox-longrun-0426-logs-256358067059"
REPORT_KEY="reports/$(date -u +%Y-%m-%d)/$(basename $FILE)"

# Upload using sandbox credentials
aws s3 cp "$FILE" "s3://$BUCKET/$REPORT_KEY" --region us-west-2

# Generate presigned URL (valid 7 days)
PRESIGNED_URL=$(aws s3 presign "s3://$BUCKET/$REPORT_KEY" --expires-in 604800 --region us-west-2)
```

## Output Format

Include in your final response:

```
📊 **Reports Generated:**
- [Report Name](presigned_url) — description
```

## Important
- ALWAYS unset AWS_ACCESS_KEY_ID/SECRET/TOKEN before uploading (revert to sandbox role)
- Upload target: `s3://sandbox-longrun-0426-logs-256358067059/reports/YYYY-MM-DD/`
- Region: us-west-2
- Presigned URLs expire in 7 days
- If upload fails, still include the text summary in your response
