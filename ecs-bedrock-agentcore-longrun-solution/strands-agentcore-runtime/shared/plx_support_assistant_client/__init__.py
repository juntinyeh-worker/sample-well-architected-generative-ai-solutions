"""
plx_support_assistant_client
--------------------
A boto3-style client for the AWS Support Interactions API.

These 6 operations are not yet in the official AWS SDK. This library
fills that gap using the same SigV4 signing mechanism boto3 uses
internally, so the interface is identical to what the real SDK will ship.

Quick start::

    from plx_support_assistant_client import get_client

    client = get_client()

    response = client.start_interaction(
        body="My EC2 instance is unreachable after a security group change"
    )
    interaction_id = response["interactionId"]

    client.update_interaction(interaction_id, "It started at 14:00 UTC today")

    entries = client.list_interaction_entries(interaction_id)
    for entry in entries["entries"]:
        print(entry)

    client.resolve_interaction(interaction_id)

Migration path
--------------
When AWS ships the official SDK, replace get_client() with::

    import boto3
    client = boto3.client("support")

All method names, parameters, and response shapes are designed to match
the real SDK so that migration requires no changes to calling code.
"""

from .client import SupportInteractionsClient
from .exceptions import (
    ClientError,
    AccessDeniedException,
    InteractionNotFoundException,
    InternalServerError,
    SubscriptionRequiredException,
    ThrottlingException,
    ValidationException,
)

__all__ = [
    "get_client",
    "SupportInteractionsClient",
    # Exceptions
    "ClientError",
    "AccessDeniedException",
    "InteractionNotFoundException",
    "InternalServerError",
    "SubscriptionRequiredException",
    "ThrottlingException",
    "ValidationException",
]

__version__ = "0.1.0"


def get_client(
    region_name: str | None = None,
    profile_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    endpoint_url: str | None = None,
) -> SupportInteractionsClient:
    """
    Factory function — returns a client for the Support Interactions API.

    Tries the official boto3 SDK first. Falls back to this shim if the
    SDK doesn't support the interaction operations yet.

    All kwargs mirror boto3.Session().client() exactly.

    :param region_name: AWS region. Defaults to us-east-1 (Support is global).
    :param profile_name: Named profile from ~/.aws/credentials.
    :param aws_access_key_id: Explicit access key (overrides credential chain).
    :param aws_secret_access_key: Explicit secret key.
    :param aws_session_token: Session token for temporary credentials.
    :param endpoint_url: Override the endpoint URL (useful for testing).

    :returns: A client with start_interaction, get_interaction,
              list_interactions, list_interaction_entries,
              update_interaction, resolve_interaction.
    """
    kwargs = dict(
        region_name=region_name,
        profile_name=profile_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        endpoint_url=endpoint_url,
    )

    # When AWS ships the SDK, start_interaction will appear on the boto3 client.
    # At that point this factory transparently switches over — zero caller changes.
    try:
        import boto3
        session_kwargs = {
            k: v for k, v in {
                "profile_name": profile_name,
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
                "aws_session_token": aws_session_token,
            }.items() if v is not None
        }
        boto3_client = boto3.Session(**session_kwargs).client(
            "support",
            region_name=region_name or "us-east-1",
            **({"endpoint_url": endpoint_url} if endpoint_url else {}),
        )
        if hasattr(boto3_client, "start_interaction"):
            return boto3_client  # type: ignore[return-value]
    except Exception:
        pass

    # SDK doesn't have it yet — use our shim
    return SupportInteractionsClient(**{k: v for k, v in kwargs.items() if v is not None})
