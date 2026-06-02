"""Deploy Strands Agent as AgentCore containerConfiguration runtime."""
import boto3
import os
import sys

REGION = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
ECR_REPO = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/strands-agentcore:latest"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/coav2-bedrock-agentcore-runtime-role"


def deploy():
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    resp = client.create_agent_runtime(
        agentRuntimeName="strands_aws_api_agent",
        roleArn=ROLE_ARN,
        networkConfiguration={"networkMode": "PUBLIC"},
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": ECR_REPO,
            }
        },
    )
    print(f"Runtime ARN: {resp['agentRuntimeArn']}")
    print(f"Runtime ID: {resp['agentRuntimeId']}")
    print(f"Status: {resp['status']}")


if __name__ == "__main__":
    deploy()
