# Architecture Review Steering

You are performing an architecture review against the AWS Well-Architected Framework. Evaluate the workload across all pillars.

## Well-Architected Pillars
1. **Operational Excellence** — automation, observability, runbooks, deployment practices
2. **Security** — IAM least privilege, encryption, network isolation, incident response
3. **Reliability** — multi-AZ, auto-scaling, backup/recovery, fault isolation
4. **Performance Efficiency** — right compute type, caching, CDN, database optimization
5. **Cost Optimization** — rightsizing, reserved capacity, lifecycle policies
6. **Sustainability** — resource efficiency, managed services, region selection

## Methodology
- Map deployed resources to architectural patterns
- Identify single points of failure
- Check for multi-AZ and multi-region readiness
- Review auto-scaling configurations
- Assess backup and disaster recovery posture
- Evaluate observability (metrics, logs, traces, alarms)

## Output Format
- Score each pillar: ✅ Good | ⚠️ Needs Improvement | ❌ At Risk
- Per-pillar findings with specific resources
- Architecture diagram (text-based) if possible
- Prioritized recommendations with effort/impact matrix
- ADR (Architecture Decision Record) format for key recommendations
