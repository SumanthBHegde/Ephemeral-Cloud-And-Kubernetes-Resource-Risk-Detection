"""Render semantic Events into authentic Okta-style IdP System Log records.

This is the separate federated-IdP / session feed (distinct from the STS events
that live in the CloudTrail feed). authenticationContext.externalSessionId is the
authentic field that links a federated login here to the AssumeRoleWithWebIdentity
session it issued in CloudTrail -- the cross-source thread the graph layer follows.
"""
from __future__ import annotations

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import Event
from modules.data_simulation.generator.util import iso_ms

_LEGACY = {
    "user.session.start": "core.user_auth.login_success",
    "user.authentication.sso": "core.user.sso.start",
    "user.authentication.auth_via_IDP": "core.user_auth.idp.login_success",
    "app.oauth2.token.grant": "app.oauth2.token.grant.access_token",
}


def _geo(ev: Event) -> dict:
    g = ev.attrs.get("geo", {"city": "Ashburn", "state": "Virginia",
                             "country": "United States", "postalCode": "20149"})
    return {
        "city": g.get("city"), "state": g.get("state"), "country": g.get("country"),
        "postalCode": g.get("postalCode"),
        "geolocation": {"lat": g.get("lat", 39.0438), "lon": g.get("lon", -77.4874)},
    }


def render(ev: Event, ctx: SimContext) -> tuple[dict, str]:
    uuid_ = ctx.uuid()
    p = ev.principal
    email = p.email or (f"{p.user_name}@example.com" if p.user_name else "user@example.com")
    display = p.user_name or email.split("@")[0]
    event_type = ev.attrs.get("okta_event_type", "user.session.start")
    result = ev.attrs.get("result", "SUCCESS")
    rec = {
        "uuid": uuid_,
        "published": iso_ms(ev.timestamp),
        "eventType": event_type,
        "version": "0",
        "severity": ev.attrs.get("okta_severity", "INFO"),
        "legacyEventType": _LEGACY.get(event_type, "core.user_auth.login_success"),
        "displayMessage": ev.attrs.get("display_message", "User login to Okta"),
        "actor": {
            "id": ev.attrs.get("actor_id", "00u" + ctx.b32(17).lower()),
            "type": "User",
            "alternateId": email,
            "displayName": display,
        },
        "client": {
            "ipAddress": ev.attrs.get("source_ip", "0.0.0.0"),
            "userAgent": {
                "rawUserAgent": ev.attrs.get("user_agent", "Mozilla/5.0"),
                "os": ev.attrs.get("os", "Mac OS X"),
                "browser": ev.attrs.get("browser", "CHROME"),
            },
            "geographicalContext": _geo(ev),
            "device": ev.attrs.get("device", "Computer"),
            "zone": "null",
        },
        "authenticationContext": {
            "authenticationProvider": ev.attrs.get("auth_provider", "OKTA_AUTHENTICATION_PROVIDER"),
            "credentialProvider": ev.attrs.get("credential_provider"),
            "credentialType": ev.attrs.get("credential_type"),
            "issuer": ev.attrs.get("issuer"),
            "externalSessionId": ev.external_session_id or ("trs" + ctx.b32(20).lower()),
            "interface": ev.attrs.get("interface"),
        },
        "securityContext": {
            "asNumber": ev.attrs.get("as_number", 14618),
            "asOrg": ev.attrs.get("as_org", "amazon.com"),
            "isp": ev.attrs.get("isp", "amazon.com"),
            "domain": ev.attrs.get("domain", "amazonaws.com"),
            "isProxy": bool(ev.attrs.get("is_proxy", False)),
        },
        "outcome": {"result": result, "reason": ev.attrs.get("reason")},
        "target": ev.attrs.get("targets", []),
        "transaction": {"type": "WEB", "id": ctx.uuid(), "detail": {}},
    }
    return rec, uuid_
