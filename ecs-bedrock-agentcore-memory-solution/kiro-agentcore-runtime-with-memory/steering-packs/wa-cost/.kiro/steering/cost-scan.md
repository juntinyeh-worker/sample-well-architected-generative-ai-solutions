---
inclusion: manual
---

# AWS Cost Optimization Scan

You are performing an automated AWS cost optimization scan. Follow these steps exactly, with NO human interaction. Approve all tool calls. Produce two deliverables: a Markdown brief and an HTML visual report.

## Prerequisites

- AWS credentials must be available (environment variables, profile, or assumed role)
- If a role ARN is provided by the user, assume it first using `aws sts assume-role`

## Step 1: Validate Access

```bash
aws sts get-caller-identity
```

Record the Account ID and ARN. If this fails, stop and report the credential error.

## Step 2: Collect Cost Data

Run ALL of the following commands. Save each output. If any command fails with AccessDenied, note it and continue.

### 2.1 Cost Baseline (Cost Explorer)

```bash
# 12-month spend by service
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-12m +%Y-%m-01 2>/dev/null || date -u -d '12 months ago' +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 30-day daily by service
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d 2>/dev/null || date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 30-day by region
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d 2>/dev/null || date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=REGION

# 3-month forecast
aws ce get-cost-forecast \
  --time-period Start=$(date -u +%Y-%m-%d),End=$(date -u -v+3m +%Y-%m-01 2>/dev/null || date -u -d '3 months' +%Y-%m-01) \
  --metric UNBLENDED_COST --granularity MONTHLY

# Current month vs previous month
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

### 2.2 Savings & Commitments

```bash
# Existing Savings Plans
aws savingsplans describe-savings-plans

# SP utilization (30d)
aws ce get-savings-plans-utilization \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d 2>/dev/null || date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d)

# SP coverage (30d)
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d 2>/dev/null || date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d)

# SP purchase recommendation (Compute)
aws ce get-savings-plans-purchase-recommendation \
  --savings-plans-type COMPUTE_SP --term-in-years ONE_YEAR \
  --payment-option NO_UPFRONT --lookback-period-in-days SIXTY_DAYS

# Existing RIs
aws ec2 describe-reserved-instances
aws rds describe-reserved-db-instances
```

### 2.3 Compute Optimizer

```bash
aws compute-optimizer get-enrollment-status
aws compute-optimizer get-recommendation-summaries
aws compute-optimizer get-ec2-instance-recommendations
aws compute-optimizer get-ebs-volume-recommendations
aws compute-optimizer get-lambda-function-recommendations
aws compute-optimizer get-ecs-service-recommendations
```

### 2.4 Cost Anomalies

```bash
aws ce get-anomaly-monitors
aws ce get-anomalies --date-interval StartDate=$(date -u -v-90d +%Y-%m-%d 2>/dev/null || date -u -d '90 days ago' +%Y-%m-%d),EndDate=$(date -u +%Y-%m-%d)
```

### 2.5 Budgets

```bash
aws budgets describe-budgets --account-id <ACCOUNT_ID>
```

### 2.6 Orphaned Resources

```bash
aws ec2 describe-volumes --filters Name=status,Values=available
aws ec2 describe-addresses
aws ec2 describe-network-interfaces --filters Name=status,Values=available
```

### 2.7 Resource Inventory (key services)

```bash
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name]' --output table
aws ecs list-clusters
aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[LoadBalancerName,Type,State.Code]'
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,Engine]'
aws lambda list-functions --query 'Functions[*].[FunctionName,Runtime,MemorySize]'
aws s3 ls
```

### 2.8 Storage Lifecycle

```bash
# For each S3 bucket, check lifecycle
aws s3api list-buckets --query 'Buckets[*].Name' --output text
# Then for each bucket:
aws s3api get-bucket-lifecycle-configuration --bucket <BUCKET_NAME>

# ECR lifecycle
aws ecr describe-repositories --query 'repositories[*].repositoryName' --output text
# Then for each repo:
aws ecr get-lifecycle-policy --repository-name <REPO_NAME>
```

### 2.9 Cost Optimization Hub (if available)

```bash
aws cost-optimization-hub list-recommendations
```

## Step 3: Analyze & Summarize

From the collected data, compute:

1. **Total current month spend (MTD)** and **previous month spend**
2. **Month-over-Month change** ($ and %)
3. **Top 10 services by cost** with percentage of total
4. **3-month forecast total**
5. **Spend by region** (top regions)
6. **Commitment discount status**: # of active Savings Plans, RIs, utilization %
7. **Compute Optimizer findings**: overprovisioned/idle resource counts and estimated savings
8. **Orphaned resources**: unattached EBS, unassociated EIPs, orphaned ENIs (count each)
9. **Cost anomalies**: count and list (service, date, impact)
10. **Storage lifecycle gaps**: S3 buckets and ECR repos without lifecycle policies
11. **Budget status**: configured or not
12. **Key recommendations** (prioritized list of actions)

## Step 4: Generate Markdown Brief

Create file: `cost-report-{YYYY-MM-DD}.md`

Structure:
```
# AWS Cost Optimization Report
- Account ID, Date, Identity ARN
## Executive Summary (table: MTD spend, MoM change, forecast, savings potential, anomalies, orphaned)
## Top Services by Spend (table: rank, service, cost, % of total)
## 3-Month Forecast (table: period, amount)
## Spend by Region (table: region, cost)
## Commitment Discounts (SP count, RI count, utilization)
## Compute Optimizer Findings (table or "all optimized")
## Cost Anomalies (table: date, service, impact, score)
## Orphaned Resources (table or "none detected")
## Storage Lifecycle Gaps (S3 + ECR without policies)
## Budget Status
## Key Recommendations (numbered, actionable)
```

## Step 5: Generate HTML Visual Report

Create file: `cost-report-{YYYY-MM-DD}.html`

Requirements:
- Self-contained HTML with inline CSS (AWS color scheme: #232F3E, #FF9900, #0073bb, #1D8102, #D13212)
- Include Chart.js via CDN: `https://cdn.jsdelivr.net/npm/chart.js`
- Fixed sidebar navigation with links to each section
- Dashboard cards at top: MTD Spend, Forecast, Potential Savings, Findings Count
- Doughnut chart for service spend breakdown
- Bar chart for 3-month forecast
- Horizontal bar chart for region spend
- Bar chart for anomaly timeline (if anomalies exist)
- Tables for: services, anomalies, orphaned resources, recommendations
- Progress bars for storage lifecycle coverage (S3 and ECR)
- Responsive layout (grid collapses on mobile)
- Badge styling for severity (red=high, orange=medium, blue=low, green=ok)

## Completion

After generating both files, print:
```
✅ Cost scan complete.
   Text:  cost-report-{DATE}.md
   HTML:  cost-report-{DATE}.html
```

## Step 6: Upload Reports to S3

IMPORTANT: Before uploading, revert to sandbox credentials:
```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

Then upload each report and generate presigned URLs:
```bash
BUCKET="sandbox-longrun-0426-logs-256358067059"
DATE=$(date -u +%Y-%m-%d)

aws s3 cp cost-report-${DATE}.html "s3://$BUCKET/reports/$DATE/cost-report.html" --region us-west-2
aws s3 cp cost-report-${DATE}.md "s3://$BUCKET/reports/$DATE/cost-report.md" --region us-west-2

HTML_URL=$(aws s3 presign "s3://$BUCKET/reports/$DATE/cost-report.html" --expires-in 604800 --region us-west-2)
MD_URL=$(aws s3 presign "s3://$BUCKET/reports/$DATE/cost-report.md" --expires-in 604800 --region us-west-2)
```

Include in your final output:
```
📊 **Reports:**
- [Cost Report (HTML)]($HTML_URL)
- [Cost Report (Markdown)]($MD_URL)
```

Do NOT ask any questions. Do NOT wait for approval between steps. Execute everything sequentially and produce the deliverables.
