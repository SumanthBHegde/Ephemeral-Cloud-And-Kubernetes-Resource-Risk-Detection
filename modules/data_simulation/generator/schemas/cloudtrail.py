"""Render semantic Events into authentic AWS CloudTrail records.

Field shapes mirror real CloudTrail (eventVersion 1.09): nested userIdentity with
sessionContext, requestParameters/responseElements per API, resources[], and
sharedEventID for cross-source linkage. Flattening for the feature pipeline is a
downstream concern -- these records stay authentic.
"""
from __future__ import annotations

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import Event
from modules.data_simulation.generator.util import iso

_EC2 = "ec2.amazonaws.com"
_STS = "sts.amazonaws.com"
_S3 = "s3.amazonaws.com"

# eventName -> (eventSource, readOnly)
_EVENT_META = {
    "RunInstances": (_EC2, False),
    "TerminateInstances": (_EC2, False),
    "AssumeRole": (_STS, False),
    "AssumeRoleWithWebIdentity": (_STS, False),
    "GetSessionToken": (_STS, True),
    "GetCallerIdentity": (_STS, True),
    "CreateBucket": (_S3, False),
    "PutBucketPolicy": (_S3, False),
    "GetObject": (_S3, True),
}


def _user_identity(ev: Event) -> dict:
    p = ev.principal
    if p.principal_type == "AssumedRole":
        role_id = p.principal_id.split(":")[0]
        return {
            "type": "AssumedRole",
            "principalId": p.principal_id,
            "arn": p.arn,
            "accountId": p.account_id,
            "accessKeyId": p.access_key_id,
            "sessionContext": {
                "sessionIssuer": {
                    "type": "Role",
                    "principalId": role_id,
                    "arn": f"arn:aws:iam::{p.account_id}:role/{p.role_name}",
                    "accountId": p.account_id,
                    "userName": p.role_name,
                },
                "attributes": {
                    "creationDate": iso(ev.attrs.get("session_creation", ev.timestamp)),
                    "mfaAuthenticated": "false",
                },
            },
        }
    if p.principal_type == "IAMUser":
        return {
            "type": "IAMUser",
            "principalId": p.principal_id,
            "arn": p.arn,
            "accountId": p.account_id,
            "accessKeyId": p.access_key_id,
            "userName": p.user_name,
        }
    if p.principal_type == "FederatedUser":
        return {
            "type": "FederatedUser",
            "principalId": p.principal_id,
            "arn": p.arn,
            "accountId": p.account_id,
        }
    # AWSService
    return {"type": "AWSService", "invokedBy": p.invoked_by or "AWS Internal"}


def _tags_items(tags: dict) -> list[dict]:
    return [{"key": k, "value": v} for k, v in tags.items()]


def _run_instances(ev: Event, ctx: SimContext):
    a = ev.attrs
    instance_id = a.get("instance_id") or ("i-" + ctx.hex(17))
    req = {
        "instancesSet": {
            "items": [{"imageId": a.get("image_id", "ami-" + ctx.hex(17)),
                       "minCount": 1, "maxCount": 1}]
        },
        "instanceType": a.get("instance_type", "t3.medium"),
        "monitoring": {"enabled": False},
    }
    if a.get("spot"):
        req["instanceMarketOptions"] = {
            "marketType": "spot",
            "spotOptions": {"spotInstanceType": "one-time"},
        }
    tags = a.get("tags") or {}
    if tags:
        req["tagSpecificationSet"] = {
            "items": [{"resourceType": "instance", "tags": _tags_items(tags)}]
        }
    nif = {"items": [{
        "privateIpAddress": a.get("private_ip", "10.0.0.10"),
    }]}
    if a.get("public_ip"):
        nif["items"][0]["association"] = {"publicIp": a["public_ip"], "ipOwnerId": "amazon"}
    resp = {
        "instancesSet": {"items": [{
            "instanceId": instance_id,
            "instanceState": {"code": 0, "name": "pending"},
            "privateIpAddress": a.get("private_ip", "10.0.0.10"),
            "networkInterfaceSet": nif,
        }]},
    }
    resources = [{"accountId": ctx.account_id, "type": "AWS::EC2::Instance",
                  "ARN": f"arn:aws:ec2:{ev.attrs.get('region', 'us-east-1')}:{ctx.account_id}:instance/{instance_id}"}]
    return req, resp, resources


def _terminate_instances(ev: Event, ctx: SimContext):
    instance_id = ev.attrs.get("instance_id") or ("i-" + ctx.hex(17))
    req = {"instancesSet": {"items": [{"instanceId": instance_id}]}}
    resp = {"instancesSet": {"items": [{
        "instanceId": instance_id,
        "currentState": {"code": 32, "name": "shutting-down"},
        "previousState": {"code": 16, "name": "running"},
    }]}}
    return req, resp, None


def _assume_role(ev: Event, ctx: SimContext):
    a = ev.attrs
    web = ev.action == "AssumeRoleWithWebIdentity"
    session = a.get("role_session_name", "session")
    role_arn = a.get("role_arn", f"arn:aws:iam::{ctx.account_id}:role/target-role")
    role_id = "AROA" + ctx.b32(17)
    req = {
        "roleArn": role_arn,
        "roleSessionName": session,
        "durationSeconds": a.get("duration_seconds", 3600),
    }
    if web:
        req["providerId"] = a.get("provider", "accounts.google.com")
    resp = {
        "credentials": {
            "accessKeyId": a.get("result_access_key_id", "ASIA" + ctx.b32(16)),
            "expiration": iso(ev.timestamp),
            "sessionToken": ctx.b32(40),
        },
        "assumedRoleUser": {
            # pinnable so a later S3 GetObject by this assumed role is linkable via principalId
            "assumedRoleId": a.get("result_assumed_role_id", f"{role_id}:{session}"),
            "arn": a.get("result_assumed_role_arn",
                         f"{role_arn.replace(':role/', ':assumed-role/')}/{session}"),
        },
    }
    if web:
        resp["subjectFromWebIdentityToken"] = a.get("web_subject", session)
        resp["audience"] = a.get("provider", "accounts.google.com")
    return req, resp, None


def _sts_simple(ev: Event, ctx: SimContext):
    if ev.action == "GetSessionToken":
        return {"durationSeconds": ev.attrs.get("duration_seconds", 3600)}, {
            "credentials": {"accessKeyId": "ASIA" + ctx.b32(16), "expiration": iso(ev.timestamp)}
        }, None
    return None, {"account": ctx.account_id, "arn": ev.principal.arn,
                  "userId": ev.principal.principal_id}, None


def _create_bucket(ev: Event, ctx: SimContext):
    bucket = ev.attrs.get("bucket_name", "bucket-" + ctx.b32(8).lower())
    req = {"bucketName": bucket, "Host": f"{bucket}.s3.amazonaws.com"}
    resources = [{"accountId": ctx.account_id, "type": "AWS::S3::Bucket",
                  "ARN": f"arn:aws:s3:::{bucket}"}]
    return req, None, resources


def _put_bucket_policy(ev: Event, ctx: SimContext):
    bucket = ev.attrs.get("bucket_name", "bucket-" + ctx.b32(8).lower())
    principal = "*" if ev.attrs.get("policy_public") else ctx.account_id
    policy = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": principal, "Action": "s3:GetObject",
        "Resource": f"arn:aws:s3:::{bucket}/*"}]}
    req = {"bucketName": bucket, "bucketPolicy": policy}
    resources = [{"accountId": ctx.account_id, "type": "AWS::S3::Bucket",
                  "ARN": f"arn:aws:s3:::{bucket}"}]
    return req, None, resources


def _get_object(ev: Event, ctx: SimContext):
    bucket = ev.attrs.get("bucket_name", "bucket-" + ctx.b32(8).lower())
    key = ev.attrs.get("key", "data/object.json")
    req = {"bucketName": bucket, "key": key, "Host": f"{bucket}.s3.amazonaws.com"}
    resources = [
        {"accountId": ctx.account_id, "type": "AWS::S3::Object",
         "ARN": f"arn:aws:s3:::{bucket}/{key}"},
        {"accountId": ctx.account_id, "type": "AWS::S3::Bucket",
         "ARN": f"arn:aws:s3:::{bucket}"},
    ]
    return req, None, resources


_RENDERERS = {
    "RunInstances": _run_instances,
    "TerminateInstances": _terminate_instances,
    "AssumeRole": _assume_role,
    "AssumeRoleWithWebIdentity": _assume_role,
    "GetSessionToken": _sts_simple,
    "GetCallerIdentity": _sts_simple,
    "CreateBucket": _create_bucket,
    "PutBucketPolicy": _put_bucket_policy,
    "GetObject": _get_object,
}


def render(ev: Event, ctx: SimContext) -> tuple[dict, str]:
    event_source, read_only = _EVENT_META[ev.action]
    req, resp, resources = _RENDERERS[ev.action](ev, ctx)
    event_id = ctx.uuid()
    region = ev.attrs.get("region") or ctx.region()
    rec = {
        "eventVersion": "1.09",
        "userIdentity": _user_identity(ev),
        "eventTime": iso(ev.timestamp),
        "eventSource": event_source,
        "eventName": ev.action,
        "awsRegion": region,
        "sourceIPAddress": ev.attrs.get("source_ip", "0.0.0.0"),
        "userAgent": ev.attrs.get("user_agent", "aws-sdk-go/1.44.0"),
        "requestParameters": req,
        "responseElements": resp,
        "requestID": ctx.uuid(),
        "eventID": event_id,
        "readOnly": read_only,
        "eventType": "AwsApiCall",
        "managementEvent": True,
        "recipientAccountId": ctx.account_id,
    }
    if resources:
        rec["resources"] = resources
    if ev.shared_event_id:
        rec["sharedEventID"] = ev.shared_event_id
    rec["tlsDetails"] = {
        "tlsVersion": "TLSv1.2",
        "cipherSuite": "ECDHE-RSA-AES128-GCM-SHA256",
        "clientProvidedHostHeader": event_source,
    }
    return rec, event_id
