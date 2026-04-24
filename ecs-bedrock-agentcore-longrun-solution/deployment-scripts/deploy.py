#!/usr/bin/env python3
"""Deploy the AgentCore Long-Running Orchestrator stack.

Two-stack model:
  1. prerequisites stack  — IAM roles + AgentCore runtime (needs iam:CreateRole)
  2. orchestrator stack   — VPC, ECS, ALB, CloudFront, CodeBuild (no IAM creation)

If the prerequisites stack already exists, its outputs are reused automatically.
"""
import argparse
import boto3
import json
import os
import sys
import time
import zipfile


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOLUTION_DIR = os.path.dirname(SCRIPT_DIR)


def get_args():
    p = argparse.ArgumentParser(description="Deploy AgentCore Long-Running Orchestrator")
    p.add_argument("--stack-name", default="sandbox-longrun")
    p.add_argument("--region", default="us-west-2")
    p.add_argument("--environment", default="prod", choices=["dev", "staging", "prod"])
    p.add_argument("--kiro-api-key", help="Kiro CLI API key (required for first deploy)")
    p.add_argument("--demo-mask-output", default="false", choices=["true", "false"])
    p.add_argument("--demo-read-only", default="false", choices=["true", "false"])
    p.add_argument("--vpc-cidr", default="10.0.0.0/16")
    # Allow skipping prerequisites if roles/runtime already exist
    p.add_argument("--task-execution-role-arn", help="Skip prerequisites: existing ECS execution role ARN")
    p.add_argument("--task-role-arn", help="Skip prerequisites: existing ECS task role ARN")
    p.add_argument("--build-role-arn", help="Skip prerequisites: existing CodeBuild role ARN")
    p.add_argument("--runtime-arn", help="Skip prerequisites: existing AgentCore runtime ARN")
    p.add_argument("--backend-image-uri", help="Pre-built backend image URI (skips build)")
    p.add_argument("--skip-frontend", action="store_true", help="Skip frontend deployment")
    return p.parse_args()


def ensure_bucket(stack_name, region):
    s3 = boto3.client("s3", region_name=region)
    account = boto3.client("sts").get_caller_identity()["Account"]
    bucket = f"{stack_name}-source-{account}-{region}"
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
        print(f"  Created bucket: {bucket}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    return bucket


def upload_sources(bucket, region):
    s3 = boto3.client("s3", region_name=region)

    # Agent source
    agent_zip = "/tmp/agent-source.zip"
    agent_dir = os.path.join(SOLUTION_DIR, "kiro-agentcore-runtime")
    with zipfile.ZipFile(agent_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(agent_dir):
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, SOLUTION_DIR))
        # Include buildspecs
        bs_dir = os.path.join(SCRIPT_DIR, "buildspecs")
        for f in os.listdir(bs_dir):
            z.write(os.path.join(bs_dir, f), f"deployment-scripts/buildspecs/{f}")
    s3.upload_file(agent_zip, bucket, "agent-source.zip")

    # Frontend source
    fe_zip = "/tmp/frontend-source.zip"
    fe_dir = os.path.join(SOLUTION_DIR, "frontend-react")
    with zipfile.ZipFile(fe_zip, "w", zipfile.ZIP_DEFLATED) as z:
        dist = os.path.join(fe_dir, "dist")
        for root, _, files in os.walk(dist):
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, fe_dir))
    s3.upload_file(fe_zip, bucket, "frontend-source.zip")
    print("  Uploaded agent-source.zip and frontend-source.zip")


def stack_outputs(cfn, name):
    try:
        resp = cfn.describe_stacks(StackName=name)
        return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    except cfn.exceptions.ClientError:
        return None


def deploy_cfn(cfn, name, template_file, params, caps=None):
    with open(template_file) as f:
        body = f.read()
    kwargs = dict(StackName=name, TemplateBody=body, Parameters=params)
    if caps:
        kwargs["Capabilities"] = caps

    existing = stack_outputs(cfn, name)
    try:
        if existing is not None:
            cfn.update_stack(**kwargs)
            print(f"  Updating {name}...")
            cfn.get_waiter("stack_update_complete").wait(StackName=name, WaiterConfig={"Delay": 15, "MaxAttempts": 80})
        else:
            cfn.create_stack(**kwargs)
            print(f"  Creating {name}...")
            cfn.get_waiter("stack_create_complete").wait(StackName=name, WaiterConfig={"Delay": 15, "MaxAttempts": 80})
    except Exception as e:
        if "No updates are to be performed" in str(e):
            print(f"  {name}: no changes")
        else:
            raise

    return stack_outputs(cfn, name)


def deploy_prerequisites(cfn, stack_name, region, source_bucket, kiro_api_key, agent_image_uri):
    prereq_name = f"{stack_name}-prereqs"
    template = os.path.join(SCRIPT_DIR, "prerequisites.yaml")

    if not os.path.exists(template):
        print(f"  prerequisites.yaml not found — skipping")
        return None

    print(f"\n=== Step 2: Prerequisites stack ({prereq_name}) ===")
    params = [
        {"ParameterKey": "StackPrefix", "ParameterValue": stack_name},
        {"ParameterKey": "SourceBucket", "ParameterValue": source_bucket},
        {"ParameterKey": "KiroApiKey", "ParameterValue": kiro_api_key},
        {"ParameterKey": "AgentContainerUri", "ParameterValue": agent_image_uri},
    ]
    return deploy_cfn(cfn, prereq_name, template, params, ["CAPABILITY_NAMED_IAM"])


def build_backend_image(stack_name, source_bucket, region):
    """Build backend image via CodeBuild and return the ECR URI."""
    account = boto3.client("sts").get_caller_identity()["Account"]
    ecr_repo = f"{account}.dkr.ecr.{region}.amazonaws.com/{stack_name}-backend"

    # Create ECR repo if needed
    ecr = boto3.client("ecr", region_name=region)
    try:
        ecr.create_repository(repositoryName=f"{stack_name}-backend", imageScanningConfiguration={"scanOnPush": True})
    except ecr.exceptions.RepositoryAlreadyExistsException:
        pass

    # Upload backend source
    be_zip = "/tmp/backend-build-source.zip"
    be_dir = os.path.join(SOLUTION_DIR, "ecs-backend")
    with zipfile.ZipFile(be_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(be_dir):
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, SOLUTION_DIR))
        z.writestr("buildspec.yml", """version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
  build:
    commands:
      - cd ecs-backend
      - docker build -t $ECR_REPO_URI:latest -f deployment/Dockerfile .
  post_build:
    commands:
      - docker push $ECR_REPO_URI:latest
""")
    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(be_zip, source_bucket, "backend-build-source.zip")

    # Create or reuse CodeBuild project
    cb = boto3.client("codebuild", region_name=region)
    project_name = f"{stack_name}-backend-build"
    try:
        cb.create_project(
            name=project_name,
            source={"type": "S3", "location": f"{source_bucket}/backend-build-source.zip"},
            artifacts={"type": "NO_ARTIFACTS"},
            environment={
                "type": "LINUX_CONTAINER", "computeType": "BUILD_GENERAL1_SMALL",
                "image": "aws/codebuild/amazonlinux2-x86_64-standard:5.0", "privilegedMode": True,
                "environmentVariables": [
                    {"name": "ECR_REPO_URI", "value": ecr_repo, "type": "PLAINTEXT"},
                    {"name": "AWS_ACCOUNT_ID", "value": account, "type": "PLAINTEXT"},
                    {"name": "AWS_DEFAULT_REGION", "value": region, "type": "PLAINTEXT"},
                ],
            },
            serviceRole=f"arn:aws:iam::{account}:role/{stack_name}-build-role",
        )
    except cb.exceptions.ResourceAlreadyExistsException:
        pass

    # Start build
    build_id = cb.start_build(projectName=project_name)["build"]["id"]
    print(f"  Build started: {build_id}")
    while True:
        status = cb.batch_get_builds(ids=[build_id])["builds"][0]["buildStatus"]
        if status != "IN_PROGRESS":
            break
        time.sleep(10)
    if status != "SUCCEEDED":
        print(f"  ERROR: Build {status}")
        sys.exit(1)
    print(f"  Build succeeded")
    return f"{ecr_repo}:latest"


def deploy_frontend(outputs, region):
    s3 = boto3.client("s3", region_name=region)
    bucket = outputs["StaticBucket"]
    dist_dir = os.path.join(SOLUTION_DIR, "frontend-react", "dist")
    ct_map = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml"}
    for root, _, files in os.walk(dist_dir):
        for f in files:
            path = os.path.join(root, f)
            key = os.path.relpath(path, dist_dir)
            ext = os.path.splitext(f)[1]
            s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": ct_map.get(ext, "application/octet-stream")})
    print(f"  Frontend deployed to s3://{bucket}")


def main():
    args = get_args()
    cfn = boto3.client("cloudformation", region_name=args.region)
    account = boto3.client("sts").get_caller_identity()["Account"]

    print(f"Deploying {args.stack_name} to {args.region} (account {account})")

    if not args.stack_name.startswith("sandbox-"):
        print("ERROR: --stack-name must start with 'sandbox-' (IAM permission boundary)")
        sys.exit(1)

    # Step 1: Source bucket + upload
    print(f"\n=== Step 1: Source bucket ===")
    bucket = ensure_bucket(args.stack_name, args.region)
    upload_sources(bucket, args.region)

    # Step 2: Resolve role ARNs and runtime ARN
    has_external = all([args.task_execution_role_arn, args.task_role_arn, args.build_role_arn, args.runtime_arn])

    if has_external:
        print(f"\n=== Step 2: Using provided role ARNs ===")
        prereq = {
            "TaskExecutionRoleArn": args.task_execution_role_arn,
            "TaskRoleArn": args.task_role_arn,
            "BuildRoleArn": args.build_role_arn,
            "AgentCoreRuntimeArn": args.runtime_arn,
        }
    else:
        # Try to read from existing prerequisites stack
        prereq_name = f"{args.stack_name}-prereqs"
        prereq = stack_outputs(cfn, prereq_name)
        if prereq and "TaskExecutionRoleArn" in prereq:
            print(f"\n=== Step 2: Reusing existing prerequisites stack ({prereq_name}) ===")
        else:
            if not args.kiro_api_key:
                print("ERROR: --kiro-api-key required for first deploy (prerequisites stack doesn't exist)")
                print("  Or provide --task-execution-role-arn, --task-role-arn, --build-role-arn, --runtime-arn")
                sys.exit(1)
            agent_uri = f"{account}.dkr.ecr.{args.region}.amazonaws.com/kiro-agentcore:latest"
            prereq = deploy_prerequisites(cfn, args.stack_name, args.region, bucket, args.kiro_api_key, agent_uri)
            if not prereq:
                print("ERROR: Prerequisites stack failed")
                sys.exit(1)

    # Step 3: Build backend image
    if args.backend_image_uri:
        backend_uri = args.backend_image_uri
        print(f"\n=== Step 3: Using provided backend image ===")
    else:
        print(f"\n=== Step 3: Building backend image ===")
        backend_uri = build_backend_image(args.stack_name, bucket, args.region)

    # Step 4: Deploy orchestrator stack
    print(f"\n=== Step 4: Orchestrator stack ({args.stack_name}) ===")
    template = os.path.join(SCRIPT_DIR, "agentcore-longrun-orchestrator-0.2.0.yaml")
    params = [
        {"ParameterKey": "Environment", "ParameterValue": args.environment},
        {"ParameterKey": "SourceBucket", "ParameterValue": bucket},
        {"ParameterKey": "BedrockRegion", "ParameterValue": args.region},
        {"ParameterKey": "DemoMaskOutput", "ParameterValue": args.demo_mask_output},
        {"ParameterKey": "DemoReadOnly", "ParameterValue": args.demo_read_only},
        {"ParameterKey": "VpcCidrBlock", "ParameterValue": args.vpc_cidr},
        {"ParameterKey": "TaskExecutionRoleArn", "ParameterValue": prereq["TaskExecutionRoleArn"]},
        {"ParameterKey": "TaskRoleArn", "ParameterValue": prereq["TaskRoleArn"]},
        {"ParameterKey": "BuildRoleArn", "ParameterValue": prereq["BuildRoleArn"]},
        {"ParameterKey": "AgentCoreRuntimeArn", "ParameterValue": prereq["AgentCoreRuntimeArn"]},
        {"ParameterKey": "BackendImageUri", "ParameterValue": backend_uri},
    ]
    outputs = deploy_cfn(cfn, args.stack_name, template, params)

    # Step 5: Deploy frontend
    if not args.skip_frontend:
        print(f"\n=== Step 5: Frontend ===")
        deploy_frontend(outputs, args.region)

    print(f"\n{'='*50}")
    print(f"✅ Deployment complete!")
    print(f"   URL: {outputs.get('CloudFrontURL', 'N/A')}")
    print(f"   ALB: {outputs.get('ALBDnsName', 'N/A')}")
    for k, v in outputs.items():
        print(f"   {k}: {v}")


if __name__ == "__main__":
    main()
