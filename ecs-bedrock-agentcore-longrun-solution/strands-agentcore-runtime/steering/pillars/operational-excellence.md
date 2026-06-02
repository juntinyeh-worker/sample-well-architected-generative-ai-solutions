# Operational Excellence Pillar Checks

## OPS-01: Resource Tagging
- Check: Resources have required tags (Environment, Owner, CostCenter)
- API: `resourcegroupstaggingapi.get_resources` (filter by missing tags)
- Warning: Resources missing mandatory tags

## OPS-02: CloudWatch Alarms
- Check: Critical services have alarms configured
- API: `cloudwatch.describe_alarms`
- Fail: No alarms for production ECS/RDS/ALB resources

## OPS-03: SSM Patch Compliance
- Check: EC2 instances are patch-compliant
- API: `ssm.describe_instance_patch_states`
- Fail: Instances with non-compliant patch status

## OPS-04: Config Rules
- Check: AWS Config is enabled with compliance rules
- API: `config.describe_config_rules`, `config.describe_compliance_by_config_rule`
- Fail: Config not enabled or critical rules non-compliant
