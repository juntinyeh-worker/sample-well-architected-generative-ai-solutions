#!/usr/bin/env python3
"""
AWS Cost Optimization — Collect & Report (No LLM Required)

Single-file script: collects AWS cost data via boto3, generates a Markdown brief
and an interactive HTML dashboard. Zero human interaction.

Usage:
    python collect-and-report.py [--profile PROFILE] [--region REGION] [--role-arn ARN]

Examples:
    python collect-and-report.py --profile my-account
    python collect-and-report.py --role-arn arn:aws:iam::123456789012:role/CostReviewReadOnly
    python collect-and-report.py  # uses default credential chain
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

def days_ago(n):
    return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")

def months_ahead(n):
    d = datetime.utcnow()
    month = d.month + n
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return datetime(year, month, 1).strftime("%Y-%m-%d")

def current_month_start():
    return datetime.utcnow().strftime("%Y-%m-01")

def prev_month_start():
    d = datetime.utcnow().replace(day=1) - timedelta(days=1)
    return d.strftime("%Y-%m-01")

def prev_month_end():
    return current_month_start()

def fmt_usd(amount):
    try:
        val = float(amount)
        return f"${val:,.2f}" if val >= 0.01 else f"${val:.4f}"
    except (TypeError, ValueError):
        return "$0.00"

def pct(part, whole):
    try:
        return (float(part) / float(whole)) * 100 if float(whole) > 0 else 0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

def safe_api(fn, label, **kwargs):
    """Call AWS API, return result or None on error."""
    try:
        return fn(**kwargs)
    except ClientError as e:
        print(f"  ⚠️  {label}: {e.response['Error']['Code']}")
        return None
    except Exception as e:
        print(f"  ⚠️  {label}: {e}")
        return None


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------

def collect(session, account_id):
    """Collect all cost optimization data. Returns a dict of results."""
    data = {}
    ce = session.client("ce")
    tp30 = {"Start": days_ago(30), "End": today_str()}

    print("\n  [1/8] Cost baseline...")
    data["current_month"] = safe_api(ce.get_cost_and_usage, "Current month",
        TimePeriod={"Start": current_month_start(), "End": today_str()},
        Granularity="MONTHLY", Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])

    data["prev_month"] = safe_api(ce.get_cost_and_usage, "Prev month",
        TimePeriod={"Start": prev_month_start(), "End": prev_month_end()},
        Granularity="MONTHLY", Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])

    data["by_region"] = safe_api(ce.get_cost_and_usage, "By region",
        TimePeriod=tp30, Granularity="MONTHLY", Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}])

    data["forecast"] = safe_api(ce.get_cost_forecast, "Forecast",
        TimePeriod={"Start": today_str(), "End": months_ahead(3)},
        Metric="UNBLENDED_COST", Granularity="MONTHLY")

    print("  [2/8] Commitments...")
    sp = session.client("savingsplans")
    data["savings_plans"] = safe_api(sp.describe_savings_plans, "Savings Plans")
    data["sp_utilization"] = safe_api(ce.get_savings_plans_utilization, "SP Util", TimePeriod=tp30)
    data["sp_coverage"] = safe_api(ce.get_savings_plans_coverage, "SP Coverage", TimePeriod=tp30)

    ec2 = session.client("ec2")
    data["ri_ec2"] = safe_api(ec2.describe_reserved_instances, "EC2 RIs")
    rds = session.client("rds")
    data["ri_rds"] = safe_api(rds.describe_reserved_db_instances, "RDS RIs")

    print("  [3/8] Compute Optimizer...")
    co = session.client("compute-optimizer")
    data["co_summaries"] = safe_api(co.get_recommendation_summaries, "CO Summaries")

    print("  [4/8] Anomalies...")
    data["anomalies"] = safe_api(ce.get_anomalies, "Anomalies",
        DateInterval={"StartDate": days_ago(90), "EndDate": today_str()})

    print("  [5/8] Budgets...")
    budgets = session.client("budgets")
    data["budgets"] = safe_api(budgets.describe_budgets, "Budgets", AccountId=account_id)

    print("  [6/8] Orphaned resources...")
    data["orphaned_ebs"] = safe_api(ec2.describe_volumes, "Unattached EBS",
        Filters=[{"Name": "status", "Values": ["available"]}])
    data["orphaned_eips"] = safe_api(ec2.describe_addresses, "EIPs")
    data["orphaned_enis"] = safe_api(ec2.describe_network_interfaces, "ENIs",
        Filters=[{"Name": "status", "Values": ["available"]}])

    print("  [7/8] Storage lifecycle...")
    s3 = session.client("s3")
    buckets_resp = safe_api(s3.list_buckets, "S3 Buckets")
    s3_lifecycle = []
    if buckets_resp:
        for b in buckets_resp.get("Buckets", [])[:20]:  # cap at 20
            name = b["Name"]
            try:
                s3.get_bucket_lifecycle_configuration(Bucket=name)
                s3_lifecycle.append({"bucket": name, "lifecycle": True})
            except ClientError:
                s3_lifecycle.append({"bucket": name, "lifecycle": False})
    data["s3_lifecycle"] = s3_lifecycle

    ecr = session.client("ecr")
    ecr_resp = safe_api(ecr.describe_repositories, "ECR Repos")
    ecr_lifecycle = []
    if ecr_resp:
        for r in ecr_resp.get("repositories", [])[:20]:
            name = r["repositoryName"]
            try:
                ecr.get_lifecycle_policy(repositoryName=name)
                ecr_lifecycle.append({"repo": name, "lifecycle": True})
            except ClientError:
                ecr_lifecycle.append({"repo": name, "lifecycle": False})
    data["ecr_lifecycle"] = ecr_lifecycle

    print("  [8/8] Cost Optimization Hub...")
    try:
        coh = session.client("cost-optimization-hub")
        data["coh_recs"] = safe_api(coh.list_recommendations, "COH Recs")
    except Exception:
        data["coh_recs"] = None

    return data


# ---------------------------------------------------------------------------
# Data Parsing
# ---------------------------------------------------------------------------

def parse(data):
    """Parse raw API responses into report-ready structures."""
    r = {
        "services": [], "total_current": 0, "total_prev": 0,
        "forecast_total": 0, "forecast_monthly": [],
        "regions": [], "anomalies": [],
        "orphaned_ebs": 0, "orphaned_eips": 0, "orphaned_enis": 0,
        "co_savings": 0, "co_findings": [],
        "sp_count": 0, "ri_ec2_count": 0, "ri_rds_count": 0,
        "sp_util_pct": None, "sp_coverage_pct": None,
        "budgets_count": 0, "coh_count": 0,
        "s3_lifecycle": data.get("s3_lifecycle", []),
        "ecr_lifecycle": data.get("ecr_lifecycle", []),
    }

    # Current month services
    if data.get("current_month"):
        for period in data["current_month"].get("ResultsByTime", []):
            for g in period.get("Groups", []):
                cost = float(g["Metrics"]["UnblendedCost"]["Amount"])
                r["services"].append({"service": g["Keys"][0], "cost": cost})
                r["total_current"] += cost
        r["services"].sort(key=lambda x: x["cost"], reverse=True)

    # Previous month
    if data.get("prev_month"):
        for period in data["prev_month"].get("ResultsByTime", []):
            for g in period.get("Groups", []):
                r["total_prev"] += float(g["Metrics"]["UnblendedCost"]["Amount"])

    # Forecast
    if data.get("forecast"):
        r["forecast_total"] = float(data["forecast"].get("Total", {}).get("Amount", 0))
        for p in data["forecast"].get("ForecastResultsByTime", []):
            r["forecast_monthly"].append({
                "period": p["TimePeriod"]["Start"][:7],
                "amount": float(p["MeanValue"])
            })

    # Regions
    if data.get("by_region"):
        for period in data["by_region"].get("ResultsByTime", []):
            for g in period.get("Groups", []):
                cost = float(g["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.001:
                    r["regions"].append({"region": g["Keys"][0], "cost": cost})
        r["regions"].sort(key=lambda x: x["cost"], reverse=True)

    # Anomalies
    if data.get("anomalies"):
        for a in data["anomalies"].get("Anomalies", []):
            r["anomalies"].append({
                "date": a.get("AnomalyStartDate", "")[:10],
                "service": a.get("DimensionValue", "Unknown"),
                "impact": a.get("Impact", {}).get("TotalImpact", 0),
                "score": a.get("AnomalyScore", {}).get("MaxScore", 0),
            })

    # Orphaned
    if data.get("orphaned_ebs"):
        r["orphaned_ebs"] = len(data["orphaned_ebs"].get("Volumes", []))
    if data.get("orphaned_eips"):
        addrs = data["orphaned_eips"].get("Addresses", [])
        r["orphaned_eips"] = len([a for a in addrs if not a.get("InstanceId")])
    if data.get("orphaned_enis"):
        r["orphaned_enis"] = len(data["orphaned_enis"].get("NetworkInterfaces", []))

    # Compute Optimizer
    if data.get("co_summaries"):
        for rec in data["co_summaries"].get("recommendationSummaries", []):
            savings_val = rec.get("aggregatedSavingsOpportunity", {}).get(
                "estimatedMonthlySavings", {}).get("value", 0)
            r["co_savings"] += savings_val
            overp = sum(int(s.get("value", 0)) for s in rec.get("summaries", [])
                       if "over" in s.get("name", "").lower() or "not" in s.get("name", "").lower())
            idle = sum(int(s.get("value", 0)) for s in rec.get("idleSummaries", [])
                      if "idle" in s.get("name", "").lower())
            if overp > 0 or idle > 0:
                r["co_findings"].append({
                    "type": rec.get("recommendationResourceType", ""),
                    "overprovisioned": overp, "idle": idle, "savings": savings_val
                })

    # Commitments
    if data.get("savings_plans"):
        r["sp_count"] = len(data["savings_plans"].get("savingsPlans", []))
    if data.get("ri_ec2"):
        r["ri_ec2_count"] = len(data["ri_ec2"].get("ReservedInstances", []))
    if data.get("ri_rds"):
        r["ri_rds_count"] = len(data["ri_rds"].get("ReservedDBInstances", []))
    if data.get("sp_utilization") and "Total" in data["sp_utilization"]:
        r["sp_util_pct"] = data["sp_utilization"]["Total"].get("Utilization", {}).get(
            "UtilizationPercentage")
    if data.get("sp_coverage") and "Total" in (data.get("sp_coverage") or {}):
        r["sp_coverage_pct"] = data["sp_coverage"]["Total"].get("Coverage", {}).get(
            "CoveragePercentage")

    # Budgets
    if data.get("budgets"):
        r["budgets_count"] = len(data["budgets"].get("Budgets", []))

    # COH
    if data.get("coh_recs"):
        r["coh_count"] = len(data["coh_recs"].get("items", []))

    return r


# ---------------------------------------------------------------------------
# Markdown Report
# ---------------------------------------------------------------------------

def generate_markdown(r, account_id, arn):
    """Generate Markdown brief."""
    mom = r["total_current"] - r["total_prev"]
    mom_pct = (mom / r["total_prev"] * 100) if r["total_prev"] > 0 else 0
    mom_sign = "+" if mom >= 0 else ""
    total_orphaned = r["orphaned_ebs"] + r["orphaned_eips"] + r["orphaned_enis"]

    lines = [
        f"# AWS Cost Optimization Report",
        f"",
        f"**Account:** {account_id}  ",
        f"**Date:** {today_str()}  ",
        f"**Identity:** `{arn}`",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Current Month (MTD) | {fmt_usd(r['total_current'])} |",
        f"| Previous Month | {fmt_usd(r['total_prev'])} |",
        f"| MoM Change | {mom_sign}{fmt_usd(mom)} ({mom_sign}{mom_pct:.1f}%) |",
        f"| 3-Month Forecast | {fmt_usd(r['forecast_total'])} |",
        f"| Compute Optimizer Savings | {fmt_usd(r['co_savings'])}/mo |",
        f"| Anomalies (90d) | {len(r['anomalies'])} |",
        f"| Orphaned Resources | {total_orphaned} |",
        f"",
        f"## Top Services (Current Month)",
        f"",
        f"| # | Service | Cost | % |",
        f"|---|---------|------|---|",
    ]
    for i, s in enumerate(r["services"][:10], 1):
        lines.append(f"| {i} | {s['service']} | {fmt_usd(s['cost'])} | {pct(s['cost'], r['total_current']):.1f}% |")

    if r["forecast_monthly"]:
        lines += ["", "## 3-Month Forecast", "", "| Period | Amount |", "|--------|--------|"]
        for f in r["forecast_monthly"]:
            lines.append(f"| {f['period']} | {fmt_usd(f['amount'])} |")
        lines.append(f"| **Total** | **{fmt_usd(r['forecast_total'])}** |")

    if r["regions"]:
        lines += ["", "## Spend by Region", "", "| Region | Cost |", "|--------|------|"]
        for reg in r["regions"][:10]:
            lines.append(f"| {reg['region']} | {fmt_usd(reg['cost'])} |")

    lines += [
        "", "## Commitment Discounts", "",
        f"- Savings Plans: **{r['sp_count']}** active" +
        (f" ({r['sp_util_pct']}% utilized)" if r["sp_util_pct"] else ""),
        f"- EC2 RIs: **{r['ri_ec2_count']}** active",
        f"- RDS RIs: **{r['ri_rds_count']}** active",
    ]

    if r["co_findings"]:
        lines += ["", "## Compute Optimizer Findings", "",
                  "| Type | Overprovisioned | Idle | Savings/mo |",
                  "|------|-----------------|------|------------|"]
        for f in r["co_findings"]:
            lines.append(f"| {f['type']} | {f['overprovisioned']} | {f['idle']} | {fmt_usd(f['savings'])} |")
    else:
        lines += ["", "## Compute Optimizer", "", "All resources optimized. No findings."]

    if r["anomalies"]:
        lines += ["", "## Anomalies (90 Days)", "",
                  "| Date | Service | Impact | Score |",
                  "|------|---------|--------|-------|"]
        for a in r["anomalies"]:
            lines.append(f"| {a['date']} | {a['service']} | {fmt_usd(a['impact'])} | {a['score']:.2f} |")

    if total_orphaned > 0:
        lines += ["", "## Orphaned Resources", "",
                  "| Type | Count |", "|------|-------|"]
        if r["orphaned_ebs"]: lines.append(f"| Unattached EBS | {r['orphaned_ebs']} |")
        if r["orphaned_eips"]: lines.append(f"| Unassociated EIPs | {r['orphaned_eips']} |")
        if r["orphaned_enis"]: lines.append(f"| Orphaned ENIs | {r['orphaned_enis']} |")

    s3_no = len([b for b in r["s3_lifecycle"] if not b["lifecycle"]])
    ecr_no = len([e for e in r["ecr_lifecycle"] if not e["lifecycle"]])
    if s3_no or ecr_no:
        lines += ["", "## Storage Lifecycle Gaps", ""]
        if s3_no: lines.append(f"- S3: **{s3_no}/{len(r['s3_lifecycle'])}** buckets without lifecycle")
        if ecr_no: lines.append(f"- ECR: **{ecr_no}/{len(r['ecr_lifecycle'])}** repos without lifecycle")

    lines += ["", "## Recommendations", ""]
    rn = 1
    if r["budgets_count"] == 0:
        lines.append(f"{rn}. Set up AWS Budgets with 80%/100% alert thresholds"); rn += 1
    if total_orphaned > 0:
        lines.append(f"{rn}. Clean up {total_orphaned} orphaned resource(s)"); rn += 1
    if s3_no:
        lines.append(f"{rn}. Add lifecycle policies to {s3_no} S3 bucket(s)"); rn += 1
    if ecr_no:
        lines.append(f"{rn}. Add lifecycle policies to {ecr_no} ECR repo(s)"); rn += 1
    if r["sp_count"] == 0 and r["ri_ec2_count"] == 0:
        lines.append(f"{rn}. Evaluate Savings Plans (20-72% savings on steady-state)"); rn += 1
    if r["co_savings"] > 0:
        lines.append(f"{rn}. Apply Compute Optimizer recs ({fmt_usd(r['co_savings'])}/mo)"); rn += 1
    if rn == 1:
        lines.append("Account is well-optimized. Continue monitoring.")

    lines += ["", "---", f"*Generated {today_str()} by collect-and-report.py*"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------

def generate_html(r, account_id):
    """Generate self-contained HTML dashboard."""
    svc_labels = json.dumps([s["service"][:28] for s in r["services"][:8]])
    svc_data = json.dumps([round(s["cost"], 2) for s in r["services"][:8]])
    colors = ["#FF9900","#0073bb","#1D8102","#D13212","#F2A900","#00a1c9","#687078","#545B64"]
    svc_colors = json.dumps(colors[:len(r["services"][:8])])

    fc_labels = json.dumps([f["period"] for f in r["forecast_monthly"]])
    fc_data = json.dumps([round(f["amount"], 2) for f in r["forecast_monthly"]])

    reg_labels = json.dumps([x["region"] for x in r["regions"][:6]])
    reg_data = json.dumps([round(x["cost"], 2) for x in r["regions"][:6]])

    mom = r["total_current"] - r["total_prev"]
    mom_pct = (mom / r["total_prev"] * 100) if r["total_prev"] > 0 else 0
    total_orphaned = r["orphaned_ebs"] + r["orphaned_eips"] + r["orphaned_enis"]
    findings = len(r["co_findings"]) + (1 if total_orphaned > 0 else 0) + len(r["anomalies"])
    mom_arrow = "&#9650;" if mom >= 0 else "&#9660;"
    mom_color = "#D13212" if mom > 0 else "#1D8102"
    mom_sign = "+" if mom >= 0 else ""

    svc_rows = ""
    for i, s in enumerate(r["services"], 1):
        p = pct(s["cost"], r["total_current"])
        c = "#FF9900" if p > 20 else "#0073bb" if p > 5 else "#1D8102"
        svc_rows += f'<tr><td>{i}</td><td>{s["service"]}</td><td class="n">{fmt_usd(s["cost"])}</td><td><div class="bw"><div class="bf" style="width:{min(p,100):.0f}%;background:{c}">{p:.1f}%</div></div></td></tr>\n'

    anom_rows = ""
    for a in r["anomalies"]:
        sc = "hri" if a["score"] > 0.5 else "mri" if a["score"] > 0.3 else "low"
        anom_rows += f'<tr><td>{a["date"]}</td><td>{a["service"]}</td><td class="n">{fmt_usd(a["impact"])}</td><td><span class="b {sc}">{a["score"]:.2f}</span></td></tr>\n'

    s3_no = len([b for b in r["s3_lifecycle"] if not b["lifecycle"]])
    s3_t = len(r["s3_lifecycle"])
    ecr_no = len([e for e in r["ecr_lifecycle"] if not e["lifecycle"]])
    ecr_t = len(r["ecr_lifecycle"])
    s3_pct = pct(s3_t - s3_no, s3_t) if s3_t else 100
    ecr_pct = pct(ecr_t - ecr_no, ecr_t) if ecr_t else 100

    recs_html = ""
    recs = []
    if r["budgets_count"] == 0: recs.append("Set up AWS Budgets with alert thresholds at 80% and 100%")
    if total_orphaned > 0: recs.append(f"Clean up {total_orphaned} orphaned resource(s) to stop waste")
    if s3_no: recs.append(f"Add lifecycle policies to {s3_no} S3 bucket(s)")
    if ecr_no: recs.append(f"Add lifecycle policies to {ecr_no} ECR repo(s)")
    if r["sp_count"] == 0 and r["ri_ec2_count"] == 0: recs.append("Evaluate Savings Plans for 20-72% savings")
    if r["co_savings"] > 0: recs.append(f"Apply Compute Optimizer recommendations ({fmt_usd(r['co_savings'])}/mo)")
    if not recs: recs.append("Account is well-optimized. Continue monitoring.")
    for rc in recs:
        recs_html += f'<div class="rc"><b>{rc}</b></div>\n'

    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Cost Report — {account_id}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{{--ink:#232F3E;--or:#FF9900;--bl:#0073bb;--gn:#1D8102;--rd:#D13212;--yl:#F2A900;--g1:#FAFAFA;--g2:#EAEDED;--g3:#D5DBDB;--g6:#687078;--g8:#37475A;--g9:#232F3E;--sw:220px}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Helvetica Neue',Arial,sans-serif;line-height:1.5;color:var(--g9);background:var(--g1);font-size:14px}}
.sb{{position:fixed;left:0;top:0;width:var(--sw);height:100vh;background:#fff;overflow-y:auto;z-index:99;box-shadow:2px 0 4px rgba(0,0,0,.06);border-right:1px solid var(--g2)}}
.sb h3{{padding:16px;background:var(--g2);border-bottom:3px solid var(--or);font-size:.95rem}}.sb p{{padding:0 16px;font-size:.75rem;color:var(--g6)}}
.sb a{{display:block;padding:7px 16px;color:var(--g8);font-size:.82rem;border-left:3px solid transparent}}.sb a:hover{{background:var(--g1);border-left-color:var(--or);color:var(--bl);text-decoration:none}}
.ct{{margin-left:var(--sw);min-height:100vh}}.cn{{max-width:1050px;margin:0 auto;padding:20px}}
.hd{{background:linear-gradient(135deg,var(--ink),var(--g8));color:#fff;padding:28px 0;text-align:center;margin-bottom:20px}}.hd h1{{font-size:1.6rem}}.hd p{{opacity:.85;font-size:.9rem}}.hd .m{{display:flex;justify-content:center;gap:16px;margin-top:8px;font-size:.78rem;opacity:.7;flex-wrap:wrap}}
.cs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}}
.cd{{background:#fff;border-radius:4px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.1);border-top:3px solid var(--or)}}.cd h4{{font-size:.75rem;color:var(--g6);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}}.cd .bg{{font-size:1.6rem;font-weight:800}}.cd .sm{{font-size:.75rem;color:var(--g6);margin-top:2px}}.cd.bl{{border-top-color:var(--bl)}}.cd.gn{{border-top-color:var(--gn)}}.cd.rd{{border-top-color:var(--rd)}}
.sc{{background:#fff;border-radius:4px;padding:20px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.08);scroll-margin-top:16px}}.sc h2{{font-size:1.2rem;font-weight:700;margin-bottom:12px;padding-bottom:5px;border-bottom:2px solid var(--or)}}
table{{width:100%;border-collapse:collapse;font-size:.82rem;margin-bottom:12px}}th{{background:var(--g2);color:var(--g8);font-weight:700;text-align:left;padding:8px 10px;border-bottom:2px solid var(--g3)}}td{{padding:7px 10px;border-bottom:1px solid var(--g2)}}td.n{{text-align:right;font-family:monospace}}tr:hover td{{background:var(--g1)}}
.b{{display:inline-block;padding:2px 7px;border-radius:10px;font-size:.7rem;font-weight:700;text-transform:uppercase}}.b.hri{{background:#fde8e8;color:var(--rd)}}.b.mri{{background:#fff3e0;color:#e65100}}.b.low{{background:#e3f2fd;color:var(--bl)}}.b.ok{{background:#e8f5e9;color:var(--gn)}}
.bw{{background:var(--g2);border-radius:6px;height:18px;overflow:hidden}}.bf{{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:6px;font-size:.68rem;font-weight:700;color:#fff}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.ch{{position:relative;height:250px;margin:10px 0}}
.rc{{background:var(--g1);border-left:4px solid var(--or);padding:10px 14px;margin-bottom:8px;border-radius:0 4px 4px 0;font-size:.85rem}}
@media(max-width:800px){{.sb{{display:none}}.ct{{margin-left:0}}.g2{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="sb"><h3>Cost Report</h3><p>{account_id} &bull; {today_str()}</p><nav>
<a href="#sum">Summary</a><a href="#svc">Services</a><a href="#fc">Forecast</a><a href="#reg">Regions</a>
<a href="#anom">Anomalies</a><a href="#co">Optimizer</a><a href="#cm">Commitments</a>
<a href="#orp">Orphaned</a><a href="#st">Storage</a><a href="#rec">Recommendations</a></nav></div>
<div class="ct"><div class="hd"><h1>AWS Cost Optimization Report</h1><p>Automated scan &mdash; {today_str()}</p><div class="m"><span>Account: {account_id}</span></div></div>
<div class="cn">
<div id="sum" class="cs">
<div class="cd"><h4>Current Month (MTD)</h4><div class="bg">{fmt_usd(r["total_current"])}</div><div class="sm" style="color:{mom_color}">{mom_arrow} {mom_sign}{mom_pct:.1f}% vs prev</div></div>
<div class="cd bl"><h4>3-Mo Forecast</h4><div class="bg">{fmt_usd(r["forecast_total"])}</div><div class="sm">~{fmt_usd(r["forecast_total"]/3 if r["forecast_total"] else 0)}/mo</div></div>
<div class="cd gn"><h4>Potential Savings</h4><div class="bg">{fmt_usd(r["co_savings"])}/mo</div><div class="sm">Compute Optimizer</div></div>
<div class="cd rd"><h4>Findings</h4><div class="bg">{findings}</div><div class="sm">{len(r["anomalies"])} anomalies, {total_orphaned} orphaned</div></div>
</div>
<div id="svc" class="sc"><h2>Spend Breakdown</h2><div class="g2"><div class="ch"><canvas id="c1"></canvas></div><div><table><thead><tr><th>#</th><th>Service</th><th>Cost</th><th>Share</th></tr></thead><tbody>{svc_rows}</tbody></table></div></div></div>
<div id="fc" class="sc"><h2>3-Month Forecast</h2><div class="ch"><canvas id="c2"></canvas></div></div>
<div id="reg" class="sc"><h2>Spend by Region</h2><div class="g2"><div class="ch"><canvas id="c3"></canvas></div><div><table><thead><tr><th>Region</th><th>Cost</th></tr></thead><tbody>{"".join(f'<tr><td>{x["region"]}</td><td class="n">{fmt_usd(x["cost"])}</td></tr>' for x in r["regions"][:10])}</tbody></table></div></div></div>
<div id="anom" class="sc"><h2>Anomalies (90 Days)</h2>{"<p><span class='b ok'>NONE</span> No anomalies detected.</p>" if not r["anomalies"] else f'<table><thead><tr><th>Date</th><th>Service</th><th>Impact</th><th>Score</th></tr></thead><tbody>{anom_rows}</tbody></table>'}</div>
<div id="co" class="sc"><h2>Compute Optimizer</h2>{"<p><span class='b ok'>ALL OPTIMIZED</span></p>" if not r["co_findings"] else '<table><thead><tr><th>Type</th><th>Overprovisioned</th><th>Idle</th><th>Savings/mo</th></tr></thead><tbody>' + "".join(f'<tr><td>{f["type"]}</td><td>{f["overprovisioned"]}</td><td>{f["idle"]}</td><td class="n">{fmt_usd(f["savings"])}</td></tr>' for f in r["co_findings"]) + '</tbody></table>'}</div>
<div id="cm" class="sc"><h2>Commitments</h2><div class="cs" style="margin:0"><div class="cd"><h4>Savings Plans</h4><div class="bg">{r["sp_count"]}</div></div><div class="cd"><h4>EC2 RIs</h4><div class="bg">{r["ri_ec2_count"]}</div></div><div class="cd"><h4>RDS RIs</h4><div class="bg">{r["ri_rds_count"]}</div></div></div>{f'<p style="margin-top:12px;color:var(--rd);font-weight:600">&#9888; No commitment discounts. Evaluate Savings Plans.</p>' if r["sp_count"]==0 and r["ri_ec2_count"]==0 else ""}</div>
<div id="orp" class="sc"><h2>Orphaned Resources</h2>{"<p><span class='b ok'>CLEAN</span> None detected.</p>" if total_orphaned==0 else f'<table><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{"".join(f"<tr><td>{t}</td><td>{c}</td></tr>" for t,c in [("Unattached EBS",r["orphaned_ebs"]),("Unassociated EIPs",r["orphaned_eips"]),("Orphaned ENIs",r["orphaned_enis"])] if c>0)}</tbody></table>'}</div>
<div id="st" class="sc"><h2>Storage Lifecycle</h2><div class="g2"><div><h4 style="font-size:.85rem;margin-bottom:6px">S3 ({s3_t} buckets)</h4><div class="bw"><div class="bf" style="width:{s3_pct:.0f}%;background:var(--gn)">{s3_pct:.0f}%</div></div><p style="font-size:.75rem;color:var(--g6);margin-top:3px">{s3_no} without lifecycle</p></div><div><h4 style="font-size:.85rem;margin-bottom:6px">ECR ({ecr_t} repos)</h4><div class="bw"><div class="bf" style="width:{ecr_pct:.0f}%;background:var(--gn)">{ecr_pct:.0f}%</div></div><p style="font-size:.75rem;color:var(--g6);margin-top:3px">{ecr_no} without lifecycle</p></div></div></div>
<div id="rec" class="sc"><h2>Recommendations</h2>{recs_html}</div>
</div></div>
<script>
new Chart(document.getElementById('c1'),{{type:'doughnut',data:{{labels:{svc_labels},datasets:[{{data:{svc_data},backgroundColor:{svc_colors},borderWidth:1}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:10}}}}}}}}}}}});
new Chart(document.getElementById('c2'),{{type:'bar',data:{{labels:{fc_labels},datasets:[{{label:'Forecast (USD)',data:{fc_data},backgroundColor:'#0073bb',borderRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,ticks:{{callback:v=>'$'+v}}}}}}}}}});
new Chart(document.getElementById('c3'),{{type:'bar',data:{{labels:{reg_labels},datasets:[{{label:'Cost',data:{reg_data},backgroundColor:'#FF9900',borderRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true,ticks:{{callback:v=>'$'+v}}}}}}}}}});
</script></body></html>'''
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AWS Cost Optimization — Collect & Report")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--role-arn", default=None, help="IAM role ARN to assume for cross-account access")
    parser.add_argument("--output-prefix", default=None, help="Output filename prefix")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  AWS Cost Optimization — Collect & Report")
    print(f"  Date: {today_str()}  Region: {args.region}")
    print(f"{'='*60}")

    # Build session
    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile

    try:
        session = boto3.Session(**session_kwargs)

        # Assume role if specified
        if args.role_arn:
            print(f"\n  Assuming role: {args.role_arn}")
            sts = session.client("sts")
            creds = sts.assume_role(
                RoleArn=args.role_arn,
                RoleSessionName="cost-scan"
            )["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=args.region
            )

        sts = session.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        arn = identity["Arn"]
        print(f"  Account: {account_id}")
        print(f"  Identity: {arn}")
    except (NoCredentialsError, ClientError) as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    # Collect
    print(f"\n  Collecting data...")
    raw = collect(session, account_id)

    # Parse
    print(f"\n  Parsing results...")
    r = parse(raw)
    print(f"  → {len(r['services'])} services, {fmt_usd(r['total_current'])} MTD")

    # Generate
    prefix = args.output_prefix or f"cost-report-{today_str()}"
    md_path = Path(f"{prefix}.md")
    html_path = Path(f"{prefix}.html")

    md_path.write_text(generate_markdown(r, account_id, arn))
    print(f"\n  ✅ {md_path}")

    html_path.write_text(generate_html(r, account_id))
    print(f"  ✅ {html_path}")

    print(f"\n{'='*60}")
    print(f"  Done. Open {html_path} in a browser.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
