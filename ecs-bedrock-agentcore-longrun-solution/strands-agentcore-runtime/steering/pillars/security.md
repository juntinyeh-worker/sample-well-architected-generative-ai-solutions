# Security Pillar Checks

## SEC-01: IAM Root Account
- Check: Root account has MFA enabled, no access keys
- API: `iam.get_account_summary`, `iam.list_mfa_devices` (for root)
- Fail: Root has access keys or no MFA

## SEC-02: IAM Password Policy
- Check: Strong password policy configured
- API: `iam.get_account_password_policy`
- Fail: MinimumPasswordLength < 14, no rotation requirement

## SEC-03: IAM Users with Console Access
- Check: Users with console access have MFA
- API: `iam.list_users`, `iam.list_mfa_devices`
- Fail: Console-enabled users without MFA

## SEC-04: S3 Public Access
- Check: S3 buckets not publicly accessible
- API: `s3.list_buckets`, `s3.get_public_access_block`, `s3.get_bucket_policy`
- Fail: Buckets with public access or open policies

## SEC-05: Encryption at Rest
- Check: EBS volumes and RDS instances encrypted
- API: `ec2.describe_volumes` (filter Encrypted=false), `rds.describe_db_instances`
- Fail: Unencrypted volumes or DB instances

## SEC-06: Security Groups
- Check: No security groups with 0.0.0.0/0 on sensitive ports
- API: `ec2.describe_security_groups`
- Fail: Ingress rules with 0.0.0.0/0 on ports 22, 3389, 3306, 5432

## SEC-07: CloudTrail
- Check: CloudTrail enabled in all regions with log validation
- API: `cloudtrail.describe_trails`, `cloudtrail.get_trail_status`
- Fail: No multi-region trail or log validation disabled

## SEC-08: GuardDuty
- Check: GuardDuty enabled
- API: `guardduty.list_detectors`
- Fail: No active detectors
