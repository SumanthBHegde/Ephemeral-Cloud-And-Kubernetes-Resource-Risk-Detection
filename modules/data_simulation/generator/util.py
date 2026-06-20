"""Small shared helpers: timestamp formatting and IP generation."""
from __future__ import annotations

import ipaddress
import random
from datetime import datetime


def iso(dt: datetime) -> str:
    """CloudTrail-style second-precision UTC timestamp, e.g. 2026-06-15T03:14:07Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ms(dt: datetime) -> str:
    """audit.k8s.io / Okta-style millisecond-precision UTC timestamp."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def private_ip(cidr: str, rng: random.Random) -> str:
    """A deterministic address drawn from a private CIDR (host part > 0)."""
    net = ipaddress.ip_network(cidr, strict=False)
    span = max(1, net.num_addresses - 2)
    return str(net.network_address + 1 + rng.randrange(span))


# AWS-ish public ranges, used for attacker staging / exposed-resource public IPs.
_PUBLIC_OCTET1 = (3, 18, 34, 52, 54)


def public_ip(rng: random.Random) -> str:
    return ".".join((
        str(rng.choice(_PUBLIC_OCTET1)),
        str(rng.randrange(0, 256)),
        str(rng.randrange(0, 256)),
        str(rng.randrange(1, 255)),
    ))
