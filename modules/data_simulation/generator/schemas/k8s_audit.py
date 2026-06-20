"""Render semantic Events into authentic Kubernetes audit.k8s.io/v1 Event records.

The detection-relevant signals live where they really do in a K8s audit log:
- metadata.ownerReferences ABSENT  -> bare pod (the Case-2 debug-pod signal)
- spec.containers[].securityContext.privileged -> privileged workload
- Service spec.type == NodePort + loadBalancerSourceRanges 0.0.0.0/0 -> public exposure
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import Event
from modules.data_simulation.generator.util import iso_ms

_VERB = {
    "pod_create": "create",
    "pod_delete": "delete",
    "service_expose": "create",
    "rbac_change": "create",
}
_CODE = {"create": 201, "delete": 200}


def _subject(ev: Event) -> dict:
    c = ev.cohort
    subject = ev.attrs.get("k8s_subject")
    if not subject:
        subject = ev.attrs.get("k8s_subject_fallback", "system:anonymous")
    if subject.startswith("system:serviceaccount:"):
        ns = subject.split(":")[2]
        groups = ["system:serviceaccounts", f"system:serviceaccounts:{ns}", "system:authenticated"]
    else:
        groups = ["system:authenticated"]
    return {"username": subject, "groups": groups,
            "uid": ev.attrs.get("subject_uid", "")}


def _owner_refs(ev: Event) -> list[dict]:
    owner = ev.attrs.get("controller_owner")
    if not owner:        # bare pod -> no controller -> the Case-2 signal
        return []
    name = ev.attrs.get("controller_name", f"{owner.lower()}-{ev.cohort}")
    return [{
        "apiVersion": "apps/v1" if owner == "ReplicaSet" else "batch/v1",
        "kind": owner,
        "name": name,
        "uid": ev.attrs.get("controller_uid", ""),
        "controller": True,
        "blockOwnerDeletion": True,
    }]


def _pod_object(ev: Event) -> dict:
    a = ev.attrs
    meta = {
        "name": a["pod_name"],
        "namespace": a["namespace"],
        "labels": a.get("labels", {}),
        "creationTimestamp": iso_ms(ev.timestamp),
    }
    owner = _owner_refs(ev)
    if owner:
        meta["ownerReferences"] = owner
    container = {
        "name": "main",
        "image": a.get("image", "registry.example.com/app:latest"),
        "ports": [{"containerPort": a.get("container_port", 8080), "protocol": "TCP"}],
        "securityContext": {
            "privileged": bool(a.get("privileged", False)),
            "runAsUser": 0 if a.get("privileged") else a.get("run_as_user", 1000),
            "allowPrivilegeEscalation": bool(a.get("privileged", False)),
        },
    }
    spec = {
        "containers": [container],
        "nodeName": a.get("node", "ip-10-0-1-20.ec2.internal"),
        "restartPolicy": a.get("restart_policy", "Always"),
        "serviceAccountName": a.get("service_account", "default"),
    }
    if a.get("host_network"):
        spec["hostNetwork"] = True
    return {"kind": "Pod", "apiVersion": "v1", "metadata": meta, "spec": spec}


def _service_object(ev: Event) -> dict:
    a = ev.attrs
    svc_type = a.get("service_type", "ClusterIP")
    spec = {
        "type": svc_type,
        "ports": [{"port": a.get("port", 80), "targetPort": a.get("container_port", 8080),
                   "protocol": "TCP"}],
        "selector": a.get("selector", {"app": a.get("service_name", "app")}),
    }
    if svc_type == "NodePort":
        spec["ports"][0]["nodePort"] = a.get("node_port", 31000)
    if svc_type == "LoadBalancer":
        spec["loadBalancerSourceRanges"] = [a.get("exposed_cidr", "0.0.0.0/0")]
        spec["externalTrafficPolicy"] = "Cluster"
    obj = {
        "kind": "Service", "apiVersion": "v1",
        "metadata": {"name": a.get("service_name", "svc"), "namespace": a["namespace"],
                     "labels": a.get("labels", {})},
        "spec": spec,
    }
    if a.get("exposed_cidr") and svc_type == "NodePort":
        # NodePort has no native source-range field; record the intended exposure authentically as an annotation
        obj["metadata"]["annotations"] = {"sim.exposure/source-ranges": a["exposed_cidr"]}
    return obj


def _rbac_object(ev: Event) -> dict:
    a = ev.attrs
    kind = a.get("rbac_kind", "RoleBinding")
    meta = {"name": a.get("rbac_name", "binding"), "namespace": a["namespace"]}
    if kind in ("Role", "ClusterRole"):
        return {"kind": kind, "apiVersion": "rbac.authorization.k8s.io/v1",
                "metadata": meta,
                "rules": a.get("rules", [{"apiGroups": [""], "resources": ["secrets"],
                                          "verbs": ["get", "list"]}])}
    return {"kind": kind, "apiVersion": "rbac.authorization.k8s.io/v1", "metadata": meta,
            "subjects": a.get("subjects", [{"kind": "ServiceAccount",
                                            "name": a.get("subject_name", "sa"),
                                            "namespace": a["namespace"]}]),
            "roleRef": a.get("role_ref", {"kind": "ClusterRole", "name": "cluster-admin",
                                          "apiGroup": "rbac.authorization.k8s.io"})}


def _ref(ev: Event):
    """(objectRef dict, requestURI, requestObject)."""
    a = ev.attrs
    ns = a["namespace"]
    if ev.action in ("pod_create", "pod_delete"):
        name = a["pod_name"]
        ref = {"resource": "pods", "namespace": ns, "name": name, "apiVersion": "v1"}
        uri = f"/api/v1/namespaces/{ns}/pods"
        if ev.action == "pod_delete":
            uri = f"{uri}/{name}"
            return ref, uri, None
        return ref, uri, _pod_object(ev)
    if ev.action == "service_expose":
        name = a.get("service_name", "svc")
        ref = {"resource": "services", "namespace": ns, "name": name, "apiVersion": "v1"}
        return ref, f"/api/v1/namespaces/{ns}/services", _service_object(ev)
    # rbac_change
    kind = a.get("rbac_kind", "RoleBinding")
    resource = {"Role": "roles", "ClusterRole": "clusterroles",
                "RoleBinding": "rolebindings", "ClusterRoleBinding": "clusterrolebindings"}[kind]
    name = a.get("rbac_name", "binding")
    ref = {"resource": resource, "namespace": ns, "name": name,
           "apiGroup": "rbac.authorization.k8s.io", "apiVersion": "v1"}
    uri = f"/apis/rbac.authorization.k8s.io/v1/namespaces/{ns}/{resource}"
    return ref, uri, _rbac_object(ev)


def render(ev: Event, ctx: SimContext) -> tuple[dict, str]:
    audit_id = ctx.uuid()
    verb = _VERB[ev.action]
    object_ref, uri, request_object = _ref(ev)
    received = ev.timestamp
    completed = received + timedelta(milliseconds=ctx.rng.randint(5, 90))
    rec = {
        "kind": "Event",
        "apiVersion": "audit.k8s.io/v1",
        "level": "RequestResponse",
        "auditID": audit_id,
        "stage": "ResponseComplete",
        "requestURI": uri,
        "verb": verb,
        "user": _subject(ev),
        "sourceIPs": [ev.attrs.get("source_ip", "10.0.0.1")],
        "userAgent": ev.attrs.get("user_agent", "kubectl/v1.29.0 (linux/amd64)"),
        "objectRef": object_ref,
        "responseStatus": {"metadata": {}, "code": _CODE[verb]},
        "requestReceivedTimestamp": iso_ms(received),
        "stageTimestamp": iso_ms(completed),
        "annotations": {
            "authorization.k8s.io/decision": "allow",
            "authorization.k8s.io/reason": ev.attrs.get("authz_reason", "RBAC: allowed"),
        },
    }
    if request_object is not None:
        rec["requestObject"] = request_object
        rec["responseObject"] = request_object
    return rec, audit_id
