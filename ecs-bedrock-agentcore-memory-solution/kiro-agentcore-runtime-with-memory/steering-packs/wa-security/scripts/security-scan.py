#!/usr/bin/env python3
"""
WA Security Quick Scan - Non-interactive AWS security assessment.

Works on any AWS account including legacy accounts without managed
security services. Uses raw resource data (IAM, SGs, S3, EBS,
CloudTrail, VPC Flow Logs) for assessment.

Produces:
  1. Markdown summary  (reports/security-scan-summary.md)
  2. HTML visual report (reports/security-scan-report.html)

Usage:
  python3 wa-security/scripts/security-scan.py [--region REGION] [--output-dir DIR]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# AWS CLI helper
# ---------------------------------------------------------------------------


def aws_cli(command, region=None):
    """Run AWS CLI command, return (data, status)."""
    parts = ["aws"] + command.split()
    if region:
        parts += ["--region", region]
    parts += ["--output", "json"]
    try:
        result = subprocess.run(parts, capture_output=True, text=True, timeout=60)
        stderr = (result.stderr or "").lower()
        if result.returncode != 0:
            if "accessdenied" in stderr or "unauthorized" in stderr:
                return None, "access_denied"
            if any(x in stderr for x in ["not subscribed", "not enabled",
                                          "optinrequired", "subscriptionrequired"]):
                return None, "not_enabled"
            if "invalidclienttokenid" in stderr or "expiredtoken" in stderr:
                return None, "auth_expired"
            return None, "error"
        if not result.stdout.strip():
            return None, "ok"
        return json.loads(result.stdout), "ok"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except (json.JSONDecodeError, FileNotFoundError):
        return None, "error"


def aws(command, region=None):
    """Convenience: return data only (None on failure)."""
    data, _ = aws_cli(command, region)
    return data


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def collect_data(region):
    """Collect all security-relevant data."""
    data = {}
    services = {}  # service -> status

    # Account identity
    data["identity"] = aws("sts get-caller-identity", region) or {}

    # IAM (global)
    data["iam_summary"] = aws("iam get-account-summary") or {}
    data["password_policy"] = aws("iam get-account-password-policy")
    data["users"] = aws("iam list-users") or {}

    # Access keys per user
    data["access_keys"] = []
    for user in data["users"].get("Users", [])[:50]:
        keys = aws(f"iam list-access-keys --user-name {user['UserName']}")
        if keys:
            for k in keys.get("AccessKeyMetadata", []):
                k["_UserName"] = user["UserName"]
                data["access_keys"].append(k)

    # CloudTrail
    data["trails"] = aws("cloudtrail describe-trails", region) or {}

    # Security Groups
    data["security_groups"] = aws("ec2 describe-security-groups", region) or {}

    # S3
    data["s3_buckets"] = aws("s3api list-buckets") or {}
    data["s3_details"] = []
    for bucket in data["s3_buckets"].get("Buckets", [])[:30]:
        name = bucket["Name"]
        detail = {"Name": name}
        detail["encryption"] = aws(f"s3api get-bucket-encryption --bucket {name}")
        detail["public_access_block"] = aws(f"s3api get-public-access-block --bucket {name}")
        detail["policy_status"] = aws(f"s3api get-bucket-policy-status --bucket {name}")
        data["s3_details"].append(detail)

    # EBS volumes
    data["ebs_volumes"] = aws("ec2 describe-volumes", region) or {}

    # VPC Flow Logs
    data["flow_logs"] = aws("ec2 describe-flow-logs", region) or {}

    # Security services status
    gd, gd_st = aws_cli("guardduty list-detectors", region)
    data["guardduty"] = gd or {}
    services["GuardDuty"] = "enabled" if gd and gd.get("DetectorIds") else "not_enabled"

    sh, sh_st = aws_cli("securityhub describe-hub", region)
    data["security_hub"] = sh
    services["Security Hub"] = "enabled" if sh else "not_enabled"

    cfg, cfg_st = aws_cli("configservice describe-configuration-recorders", region)
    data["config"] = cfg or {}
    services["AWS Config"] = "enabled" if (cfg or {}).get("ConfigurationRecorders") else "not_enabled"

    data["_services"] = services
    return data


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


class Finding:
    def __init__(self, severity, title, description, recommendation,
                 category="General", source="raw"):
        self.severity = severity
        self.title = title
        self.description = description
        self.recommendation = recommendation
        self.category = category
        self.source = source  # "raw" or "service"


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze(data):
    """Run all security checks and return findings."""
    findings = []
    now = datetime.now(timezone.utc)

    # --- Root account access keys ---
    summary_map = data.get("iam_summary", {}).get("SummaryMap", {})
    if summary_map.get("AccountAccessKeysPresent", 0) > 0:
        findings.append(Finding(
            "CRITICAL",
            "Root Account Has Active Access Keys",
            "The root account has active access keys. Root credentials should never be used programmatically.",
            "Delete root access keys immediately. Use IAM users/roles for all API access.",
            category="IAM",
        ))

    # --- Access key age ---
    old_keys = []
    for key in data.get("access_keys", []):
        if key.get("Status") != "Active":
            continue
        created = key.get("CreateDate", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age = (now - dt).days
                if age > 90:
                    old_keys.append((key["_UserName"], age))
            except (ValueError, TypeError):
                pass
    if old_keys:
        details = "; ".join([f"{u} ({d}d)" for u, d in old_keys[:5]])
        extra = f" +{len(old_keys)-5} more" if len(old_keys) > 5 else ""
        findings.append(Finding(
            "HIGH",
            f"Access Keys Not Rotated ({len(old_keys)})",
            f"Active keys older than 90 days: {details}{extra}.",
            "Rotate access keys every 90 days. Prefer IAM roles over long-lived keys.",
            category="IAM",
        ))

    # --- MFA coverage ---
    users_count = summary_map.get("Users", 0)
    mfa_count = summary_map.get("MFADevicesInUse", 0)
    if users_count > 0 and mfa_count < users_count:
        gap = users_count - mfa_count
        findings.append(Finding(
            "HIGH",
            f"IAM Users Without MFA ({gap}/{users_count})",
            f"{gap} IAM user(s) do not have MFA enabled.",
            "Enable MFA for all users. Enforce MFA via IAM policy conditions.",
            category="IAM",
        ))

    # --- Password policy ---
    if not data.get("password_policy"):
        findings.append(Finding(
            "MEDIUM",
            "No Custom Password Policy",
            "No custom IAM password policy. Default allows weak passwords.",
            "Set min 14 chars, require complexity, enable 90-day expiration, prevent reuse.",
            category="IAM",
        ))

    # --- Security Groups: SSH/RDP open ---
    sgs = data.get("security_groups", {}).get("SecurityGroups", [])
    critical_rules = []
    high_rules = []
    for sg in sgs:
        sg_id = sg.get("GroupId", "")
        sg_name = sg.get("GroupName", "")
        for rule in sg.get("IpPermissions", []):
            port = rule.get("FromPort", "all")
            all_ranges = rule.get("IpRanges", []) + rule.get("Ipv6Ranges", [])
            for r in all_ranges:
                cidr = r.get("CidrIp", r.get("CidrIpv6", ""))
                if cidr in ("0.0.0.0/0", "::/0"):
                    entry = f"{sg_name}({sg_id}) port {port}"
                    if port in (22, 3389):
                        critical_rules.append(entry)
                    elif port not in (80, 443, None, -1):
                        high_rules.append(entry)

    if critical_rules:
        details = "; ".join(critical_rules[:5])
        findings.append(Finding(
            "CRITICAL",
            f"SSH/RDP Open to Internet ({len(critical_rules)})",
            f"Security groups allow SSH/RDP from 0.0.0.0/0: {details}.",
            "Restrict to specific IPs or use SSM Session Manager for remote access.",
            category="Network",
        ))
    if high_rules:
        details = "; ".join(high_rules[:5])
        extra = f" +{len(high_rules)-5} more" if len(high_rules) > 5 else ""
        findings.append(Finding(
            "HIGH",
            f"Non-Standard Ports Open to Internet ({len(high_rules)})",
            f"Ports other than 80/443 exposed to 0.0.0.0/0: {details}{extra}.",
            "Restrict inbound rules to known IP ranges.",
            category="Network",
        ))

    # --- S3: encryption and public access ---
    unencrypted = []
    public = []
    for d in data.get("s3_details", []):
        name = d["Name"]
        if not d.get("encryption"):
            unencrypted.append(name)
        pab = d.get("public_access_block")
        if pab:
            cfg = pab.get("PublicAccessBlockConfiguration", {})
            if not all([cfg.get("BlockPublicAcls"), cfg.get("BlockPublicPolicy"),
                        cfg.get("IgnorePublicAcls"), cfg.get("RestrictPublicBuckets")]):
                public.append(name)
        else:
            public.append(name)
        ps = d.get("policy_status")
        if ps and ps.get("PolicyStatus", {}).get("IsPublic") and name not in public:
            public.append(name)

    if public:
        names = ", ".join(public[:5])
        extra = f" +{len(public)-5}" if len(public) > 5 else ""
        findings.append(Finding(
            "HIGH",
            f"S3 Buckets Potentially Public ({len(public)})",
            f"Buckets without full public access block: {names}{extra}.",
            "Enable S3 Block Public Access at account level and per bucket.",
            category="Data Protection",
        ))
    if unencrypted:
        names = ", ".join(unencrypted[:5])
        extra = f" +{len(unencrypted)-5}" if len(unencrypted) > 5 else ""
        findings.append(Finding(
            "MEDIUM",
            f"S3 Buckets Without Encryption ({len(unencrypted)})",
            f"No default encryption: {names}{extra}.",
            "Enable SSE-S3 or SSE-KMS default encryption on all buckets.",
            category="Data Protection",
        ))

    # --- EBS: unencrypted volumes ---
    volumes = data.get("ebs_volumes", {}).get("Volumes", [])
    unenc_vols = [v for v in volumes if not v.get("Encrypted")]
    if unenc_vols:
        findings.append(Finding(
            "MEDIUM",
            f"Unencrypted EBS Volumes ({len(unenc_vols)})",
            f"{len(unenc_vols)} EBS volume(s) not encrypted at rest.",
            "Enable EBS encryption by default. Migrate unencrypted volumes to encrypted copies.",
            category="Data Protection",
        ))

    # --- VPC Flow Logs ---
    if not data.get("flow_logs", {}).get("FlowLogs"):
        findings.append(Finding(
            "MEDIUM",
            "No VPC Flow Logs",
            "No VPC Flow Logs detected. Network traffic is not logged for forensic analysis.",
            "Enable VPC Flow Logs on all VPCs, send to CloudWatch Logs or S3.",
            category="Detective Controls",
        ))

    # --- CloudTrail ---
    trails = data.get("trails", {}).get("trailList", [])
    if not trails:
        findings.append(Finding(
            "CRITICAL",
            "CloudTrail Not Configured",
            "No CloudTrail trails. API activity is not being logged.",
            "Create a multi-region trail with log file validation enabled.",
            category="Detective Controls",
        ))
    else:
        if not any(t.get("IsMultiRegionTrail") for t in trails):
            findings.append(Finding(
                "MEDIUM",
                "No Multi-Region CloudTrail",
                "CloudTrail exists but is not multi-region.",
                "Enable multi-region logging to capture activity in all regions.",
                category="Detective Controls",
            ))
        if not any(t.get("LogFileValidationEnabled") for t in trails):
            findings.append(Finding(
                "LOW",
                "CloudTrail Log Validation Disabled",
                "Log file integrity validation not enabled.",
                "Enable log file validation to detect tampered logs.",
                category="Detective Controls",
            ))

    # --- Security service status (recommendations) ---
    if not data.get("guardduty", {}).get("DetectorIds"):
        findings.append(Finding(
            "HIGH",
            "GuardDuty Not Enabled",
            "GuardDuty is not enabled. Threat detection for compromised instances and credential exfiltration unavailable.",
            "Enable GuardDuty (30-day free trial, no agents required).",
            category="Security Services", source="service",
        ))
    if not data.get("security_hub"):
        findings.append(Finding(
            "MEDIUM",
            "Security Hub Not Enabled",
            "Security Hub not enabled. No centralized security findings view.",
            "Enable Security Hub with AWS Foundational Security Best Practices standard.",
            category="Security Services", source="service",
        ))
    if not data.get("config", {}).get("ConfigurationRecorders"):
        findings.append(Finding(
            "MEDIUM",
            "AWS Config Not Enabled",
            "AWS Config not recording. Configuration drift undetectable.",
            "Enable Config with recording for all resource types.",
            category="Security Services", source="service",
        ))

    # Positive note if nothing critical
    if not any(f.severity == "CRITICAL" for f in findings):
        findings.append(Finding(
            "INFO",
            "No Critical Security Issues",
            "No critical security misconfigurations detected from raw resource data.",
            "Continue monitoring and enable advanced security services for deeper visibility.",
            category="General",
        ))

    return findings


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def generate_markdown(account_info, findings, services):
    """Generate Markdown report."""
    lines = []
    lines.append("# WA Security Quick Scan Report")
    lines.append("")
    lines.append(f"**Account**: {account_info['account_id']}")
    lines.append(f"**Region**: {account_info['region']}")
    lines.append(f"**Scan Time**: {account_info['scan_time']}")
    lines.append(f"**Identity**: {account_info['arn']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Environment
    lines.append("## Environment Profile")
    lines.append("")
    lines.append("| Service | Status |")
    lines.append("|---------|--------|")
    for svc, status in sorted(services.items()):
        icon = {"enabled": "✅", "not_enabled": "⚠️", "access_denied": "🔒"}.get(status, "❓")
        lines.append(f"| {svc} | {icon} {status} |")
    lines.append("")
    lines.append("> Findings tagged `[raw]` are from actual resource data and valid regardless of service enablement.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "ℹ️"}[sev]
        lines.append(f"| {icon} {sev} | {sev_counts[sev]} |")
    lines.append("")
    lines.append(f"**Total**: {len(findings)} findings")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Findings by category
    categories = []
    for f in findings:
        if f.category not in categories:
            categories.append(f.category)

    for cat in categories:
        cat_findings = [f for f in findings if f.category == cat]
        lines.append(f"## {cat}")
        lines.append("")
        for f in cat_findings:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "ℹ️"}.get(f.severity, "")
            tag = f" `[{f.source}]`" if f.severity != "INFO" else ""
            lines.append(f"### {icon} [{f.severity}] {f.title}{tag}")
            lines.append("")
            lines.append(f"{f.description}")
            lines.append("")
            lines.append(f"**Recommendation**: {f.recommendation}")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. **Immediate**: Fix CRITICAL findings (root keys, open SSH, missing CloudTrail)")
    lines.append("2. **Week 1**: Enable GuardDuty, AWS Config, Security Hub")
    lines.append("3. **30 days**: Remediate HIGH and MEDIUM findings")
    lines.append("4. **Quarterly**: Re-run scan and track improvement")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated on {account_info['scan_time']}*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def generate_html(account_info, findings, services):
    """Generate self-contained HTML report."""
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    # Service rows
    svc_rows = ""
    for svc, status in sorted(services.items()):
        color = {"enabled": "#1D8102", "not_enabled": "#FF9900", "access_denied": "#D13212"}.get(status, "#687078")
        svc_rows += f'<tr><td>{svc}</td><td style="color:{color};font-weight:600;">{status}</td></tr>\n'

    # Category nav + findings
    categories = []
    for f in findings:
        if f.category not in categories:
            categories.append(f.category)

    nav_html = ""
    for cat in categories:
        cid = cat.lower().replace(" ", "-")
        nav_html += f'<a class="nav-link" href="#{cid}">{cat}</a>\n'

    findings_html = ""
    for cat in categories:
        cid = cat.lower().replace(" ", "-")
        cat_findings = [f for f in findings if f.category == cat]
        findings_html += f'<div class="section" id="{cid}"><h2>{cat}</h2>\n'
        for f in cat_findings:
            sev_class = f"sev-{f.severity.lower()}"
            border = {"CRITICAL": "#D13212", "HIGH": "#FF9900", "MEDIUM": "#F2C94C",
                      "LOW": "#0073bb", "INFO": "#687078"}.get(f.severity, "#687078")
            badge = ""
            if f.severity != "INFO":
                bc = "#2196F3" if f.source == "raw" else "#9C27B0"
                badge = f'<span class="src-badge" style="background:{bc};">{f.source}</span>'
            findings_html += f'''<div class="finding" style="border-left-color:{border};">
  <div class="f-header"><span class="f-title">{f.title} {badge}</span><span class="f-sev {sev_class}">{f.severity}</span></div>
  <p class="f-desc">{f.description}</p>
  <div class="f-rec"><strong>Recommendation:</strong> {f.recommendation}</div>
</div>\n'''
        findings_html += '</div>\n'

    raw_count = sum(1 for f in findings if f.source == "raw" and f.severity != "INFO")
    svc_count = sum(1 for f in findings if f.source == "service" and f.severity != "INFO")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WA Security Scan - {account_info["account_id"]}</title>
<style>
:root {{ --orange:#FF9900; --blue:#0073bb; --red:#D13212; --green:#1D8102; --ink:#232F3E; --g50:#FAFAFA; --g100:#F2F3F3; --g200:#EAEDED; --g600:#687078; --g700:#545B64; --g800:#37475A; --g900:#232F3E; --side:250px; }}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:var(--g900);background:var(--g50);font-size:14px;}}
.side{{position:fixed;left:0;top:0;width:var(--side);height:100vh;background:#fff;border-right:1px solid var(--g200);overflow-y:auto;z-index:100;}}
.side-hdr{{padding:18px;background:var(--g100);border-bottom:2px solid var(--orange);}}
.side-hdr h3{{font-size:1rem;}} .side-hdr p{{font-size:0.78rem;color:var(--g600);margin-top:3px;}}
.nav-link{{display:block;padding:9px 18px;color:var(--g700);text-decoration:none;font-size:0.85rem;border-left:3px solid transparent;}}
.nav-link:hover{{background:var(--g100);border-left-color:var(--orange);color:var(--blue);}}
.main{{margin-left:var(--side);}}
.hdr{{background:linear-gradient(135deg,var(--ink),var(--g800));color:#fff;padding:36px 28px;text-align:center;}}
.hdr h1{{font-size:1.8rem;margin-bottom:6px;}} .hdr p{{opacity:0.9;font-size:0.95rem;}}
.wrap{{max-width:1000px;margin:0 auto;padding:28px;}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:28px;}}
.card{{background:#fff;border-radius:4px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08);border-top:3px solid var(--orange);}}
.card .n{{font-size:1.7rem;font-weight:700;}} .card .l{{font-size:0.78rem;color:var(--g600);margin-top:3px;}}
.section{{background:#fff;border-radius:4px;padding:22px;margin-bottom:22px;box-shadow:0 1px 3px rgba(0,0,0,.08);scroll-margin-top:16px;}}
.section h2{{font-size:1.2rem;margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--orange);}}
.finding{{border-left:4px solid var(--blue);padding:12px 14px;margin-bottom:10px;background:var(--g50);border-radius:0 4px 4px 0;}}
.f-header{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap;}}
.f-title{{font-weight:600;font-size:0.92rem;flex:1;}}
.f-sev{{padding:2px 9px;border-radius:3px;font-size:0.7rem;font-weight:700;text-transform:uppercase;color:#fff;white-space:nowrap;}}
.sev-critical{{background:#D13212;}} .sev-high{{background:#FF9900;}} .sev-medium{{background:#F2C94C;color:#333;}} .sev-low{{background:#0073bb;}} .sev-info{{background:#687078;}}
.f-desc{{color:var(--g700);font-size:0.88rem;margin-bottom:6px;}}
.f-rec{{background:#e8f5e9;border-radius:4px;padding:8px 10px;font-size:0.85rem;}}
.src-badge{{color:#fff;padding:1px 6px;border-radius:3px;font-size:0.68rem;margin-left:6px;vertical-align:middle;}}
.env-tbl{{width:100%;border-collapse:collapse;margin:8px 0;}} .env-tbl td{{padding:5px 10px;border-bottom:1px solid var(--g200);font-size:0.88rem;}}
.footer{{text-align:center;padding:18px;color:var(--g600);border-top:1px solid var(--g200);margin-top:28px;font-size:0.82rem;}}
@media(max-width:768px){{.side{{display:none;}}.main{{margin-left:0;}}}}
@media print{{.side{{display:none;}}.main{{margin-left:0;}}.section{{break-inside:avoid;}}}}
</style>
</head>
<body>
<div class="side">
  <div class="side-hdr"><h3>WA Security Scan</h3><p>{account_info["account_id"]}<br>{account_info["region"]}</p></div>
  <div style="padding:10px 0;">
    <a class="nav-link" href="#summary">Summary</a>
    <a class="nav-link" href="#environment">Environment</a>
    {nav_html}
  </div>
</div>
<div class="main">
  <div class="hdr">
    <h1>WA Security Quick Scan</h1>
    <p>{account_info["account_id"]} &bull; {account_info["region"]} &bull; {account_info["scan_time"][:10]}</p>
  </div>
  <div class="wrap">
    <div class="section" id="summary">
      <h2>Summary</h2>
      <div class="cards">
        <div class="card"><div class="n" style="color:#D13212;">{sev_counts["CRITICAL"]}</div><div class="l">Critical</div></div>
        <div class="card"><div class="n" style="color:#FF9900;">{sev_counts["HIGH"]}</div><div class="l">High</div></div>
        <div class="card"><div class="n" style="color:#F2C94C;">{sev_counts["MEDIUM"]}</div><div class="l">Medium</div></div>
        <div class="card"><div class="n" style="color:#0073bb;">{sev_counts["LOW"]}</div><div class="l">Low</div></div>
        <div class="card"><div class="n" style="color:#687078;">{sev_counts["INFO"]}</div><div class="l">Info</div></div>
        <div class="card"><div class="n">{len(findings)}</div><div class="l">Total</div></div>
      </div>
      <p style="font-size:0.85rem;color:var(--g600);">
        <span class="src-badge" style="background:#2196F3;">raw</span> {raw_count} from resource data &nbsp;
        <span class="src-badge" style="background:#9C27B0;">service</span> {svc_count} from service status
      </p>
    </div>

    <div class="section" id="environment">
      <h2>Environment Profile</h2>
      <p style="font-size:0.85rem;color:var(--g600);margin-bottom:10px;">
        Shows security service availability. <span class="src-badge" style="background:#2196F3;">raw</span> findings
        are valid regardless of service status.
      </p>
      <table class="env-tbl">{svc_rows}</table>
    </div>

    {findings_html}

    <div class="section">
      <h2>Next Steps</h2>
      <ol style="margin-left:18px;line-height:2;font-size:0.92rem;">
        <li><strong>Immediate</strong>: Fix CRITICAL findings (root keys, open SSH/RDP, missing CloudTrail)</li>
        <li><strong>Week 1</strong>: Enable GuardDuty, AWS Config, Security Hub</li>
        <li><strong>30 days</strong>: Remediate HIGH and MEDIUM findings</li>
        <li><strong>Quarterly</strong>: Re-run scan and track improvement</li>
      </ol>
    </div>
  </div>
  <div class="footer">
    WA Security Quick Scan &bull; {account_info["scan_time"]}<br>
    Automated assessment using raw resource data. Works on legacy accounts without managed security services.
  </div>
</div>
</body>
</html>'''
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="WA Security Quick Scan - Non-interactive AWS security assessment")
    parser.add_argument("--region", default="us-east-1",
                        help="AWS region (default: us-east-1)")
    parser.add_argument("--output-dir", default="wa-security/reports",
                        help="Output directory (default: wa-security/reports)")
    args = parser.parse_args()

    region = args.region
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print("  WA Security Quick Scan")
    print("=" * 56)
    print()

    # Verify credentials
    print("[1/3] Verifying AWS credentials...")
    identity = aws("sts get-caller-identity", region)
    if not identity:
        print("ERROR: Cannot authenticate. Check AWS credentials.")
        print("  Run: aws sts get-caller-identity")
        sys.exit(1)

    account_info = {
        "account_id": identity.get("Account", "Unknown"),
        "arn": identity.get("Arn", "Unknown"),
        "region": region,
        "scan_time": datetime.now(timezone.utc).isoformat(),
    }
    print(f"  Account: {account_info['account_id']}")
    print(f"  Region:  {region}")
    print()

    # Collect
    print("[2/3] Collecting security data...")
    print("  - IAM users, keys, MFA, password policy")
    print("  - Security groups, VPC flow logs")
    print("  - S3 buckets (encryption, public access)")
    print("  - EBS volumes, CloudTrail")
    print("  - Security service status")
    data = collect_data(region)
    services = data.get("_services", {})

    print()
    print("  Service availability:")
    for svc, status in sorted(services.items()):
        icon = {"enabled": "+", "not_enabled": "-", "access_denied": "x"}.get(status, "?")
        print(f"    [{icon}] {svc}: {status}")
    print()

    # Analyze
    print("[3/3] Analyzing...")
    findings = analyze(data)

    # Sort by severity
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    findings.sort(key=lambda f: sev_order.get(f.severity, 5))

    print(f"  Findings: {len(findings)}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        c = sum(1 for f in findings if f.severity == sev)
        if c:
            print(f"    {sev}: {c}")
    print()

    # Generate reports
    print("Generating reports...")
    md = generate_markdown(account_info, findings, services)
    md_path = output_dir / "security-scan-summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  {md_path}")

    html = generate_html(account_info, findings, services)
    html_path = output_dir / "security-scan-report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  {html_path}")

    print()
    print("=" * 56)
    print(f"  Done! Open {html_path} in a browser.")
    print("=" * 56)


if __name__ == "__main__":
    main()
