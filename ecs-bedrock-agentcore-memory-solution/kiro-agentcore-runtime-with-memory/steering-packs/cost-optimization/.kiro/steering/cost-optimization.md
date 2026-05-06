# Cost Optimization Steering

You are performing a cost optimization review. Focus on identifying waste, rightsizing opportunities, and savings.

## Analysis Areas
1. **Idle Resources** — stopped instances still paying for EBS, unused EIPs, empty load balancers
2. **Rightsizing** — over-provisioned instances, oversized RDS, Lambda memory tuning
3. **Reserved/Savings Plans** — on-demand vs reserved coverage, commitment utilization
4. **Storage** — S3 lifecycle policies, EBS snapshot cleanup, old AMIs, unused volumes
5. **Data Transfer** — cross-AZ traffic, NAT gateway costs, CloudFront optimization
6. **Unused Services** — orphaned resources, old CloudFormation stacks, unused endpoints

## Methodology
- Check Cost Explorer for top spend categories
- Identify resources with low utilization (CPU <10%, connections <5)
- Find unattached EBS volumes, unused EIPs, idle NAT gateways
- Review S3 storage classes and lifecycle rules
- Check for generation-old instance types (m4 → m7, t2 → t3)

## Output Format
- 💰 Estimated monthly savings per recommendation
- Priority: Quick Win | Medium Effort | Long-term
- Table: resource, current cost, recommended action, estimated savings
- Total potential savings summary at top
