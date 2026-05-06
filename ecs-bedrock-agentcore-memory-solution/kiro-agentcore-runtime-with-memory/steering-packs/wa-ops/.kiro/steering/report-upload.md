---
inclusion: auto
---

# Report Upload Instructions

After generating any report files (.html, .md, .pdf), upload them to S3 and provide presigned URLs.

## Upload Procedure

For EACH generated report file:

```bash
# Upload to the reports bucket
BUCKET="${TASK_LOG_BUCKET:-sandbox-longrun-0426-logs-256358067059}"
REPORT_KEY="reports/$(date -u +%Y-%m-%d)/$(basename $FILE)"
aws s3 cp "$FILE" "s3://$BUCKET/$REPORT_KEY"

# Generate a presigned URL (valid 7 days)
PRESIGNED_URL=$(aws s3 presign "s3://$BUCKET/$REPORT_KEY" --expires-in 604800)
```

## Output Format

After uploading, include in your final response:

```
📊 **Reports Generated:**
- [Report Name](presigned_url) — description
```

Always include the presigned URL so the user can download/view the report directly in their browser.

## Important
- Use the TASK_LOG_BUCKET environment variable if available, otherwise use `sandbox-longrun-0426-logs-256358067059`
- Reports go under the `reports/YYYY-MM-DD/` prefix
- Presigned URLs expire in 7 days (604800 seconds)
- If S3 upload fails, still include the text summary in your response
