# Reliability Pillar Checks

## REL-01: Multi-AZ Deployments
- Check: RDS instances use Multi-AZ
- API: `rds.describe_db_instances`
- Fail: Production DBs without MultiAZ=true

## REL-02: Auto Scaling
- Check: EC2/ECS services have auto scaling configured
- API: `autoscaling.describe_auto_scaling_groups`, `application-autoscaling.describe_scalable_targets`
- Fail: Production workloads with fixed capacity

## REL-03: Backup Configuration
- Check: AWS Backup plans exist for critical resources
- API: `backup.list_backup_plans`, `backup.list_protected_resources`
- Fail: Critical resources (RDS, EBS, DynamoDB) not protected

## REL-04: Health Checks
- Check: ALB/NLB have health checks configured with appropriate thresholds
- API: `elbv2.describe_target_groups`, `elbv2.describe_target_health`
- Fail: Unhealthy targets or missing health checks

## REL-05: Cross-Region Strategy
- Check: Critical workloads have cross-region backup or failover
- API: `rds.describe_db_instances` (ReadReplicaDBInstanceIdentifiers), `s3.get_bucket_replication`
- Info: Document cross-region posture
