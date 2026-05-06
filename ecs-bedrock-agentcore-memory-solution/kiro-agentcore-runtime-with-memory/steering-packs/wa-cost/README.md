# wa-cost — Minimal Cost Optimization Steering Pack for Kiro CLI

A lightweight, drop-in steering pack that scans an AWS account (via assumed role), collects cost intelligence data, produces a text brief, and generates an interactive HTML report. No human interaction required.

## Usage

```bash
# Drop into any Kiro CLI workspace
cp -r wa-cost/.kiro .kiro

# Then run with Kiro CLI
kiro-cli "Scan AWS account using the assumed role, generate cost report"
```

Or if you already have `.kiro/steering/`, just copy the steering file:

```bash
cp wa-cost/.kiro/steering/cost-scan.md .kiro/steering/
```

## What it does

1. Assumes the IAM role (or uses current credentials)
2. Runs ~50 read-only AWS API calls across Cost Explorer, Compute Optimizer, and resource APIs
3. Produces a Markdown brief with key findings
4. Generates a self-contained HTML dashboard

## Required IAM Permissions

The assumed role needs:

```
ReadOnlyAccess (AWS managed)
+ ce:Get*, ce:List*, ce:Describe*
+ budgets:Describe*, budgets:ViewBudget
+ savingsplans:Describe*
+ cost-optimization-hub:List*, cost-optimization-hub:Get*
+ compute-optimizer:Get*, compute-optimizer:Describe*
+ cur:Describe*
+ bcm-data-exports:List*, bcm-data-exports:Get*
+ support:DescribeTrustedAdvisor* (optional, requires Business/Enterprise Support)
```

## Files

```
wa-cost/
├── .kiro/
│   └── steering/
│       └── cost-scan.md          # The steering file (entry point for Kiro CLI)
├── collect-and-report.py         # Standalone Python script (no LLM needed)
└── README.md                     # This file
```
