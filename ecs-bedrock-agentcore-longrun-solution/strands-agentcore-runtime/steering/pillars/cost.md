# Cost Optimization Pillar Checks

## COST-01: Unused Resources
- Check: Identify unattached EBS volumes, unused EIPs, idle load balancers
- API: `ec2.describe_volumes` (status=available), `ec2.describe_addresses` (no association), `elbv2.describe_target_health`
- Fail: Resources incurring cost with no usage

## COST-02: Right-Sizing
- Check: EC2 instances with low CPU/memory utilization
- API: `cloudwatch.get_metric_statistics` (CPUUtilization < 10% over 14 days)
- Warning: Instances consistently underutilized

## COST-03: Reserved/Savings Plans Coverage
- Check: Coverage of on-demand spend by commitments
- API: `ce.get_savings_plans_coverage`, `ce.get_reservation_coverage`
- Info: Current coverage percentage and potential savings

## COST-04: S3 Storage Classes
- Check: Large buckets using appropriate storage tiers
- API: `s3.list_buckets`, `cloudwatch.get_metric_statistics` (BucketSizeBytes)
- Warning: Large buckets without lifecycle policies

## COST-05: Stopped Resources Still Costing
- Check: Stopped EC2 with attached EBS, NAT Gateways with no traffic
- API: `ec2.describe_instances` (state=stopped), `ec2.describe_nat_gateways`
- Warning: Stopped instances with large EBS volumes
