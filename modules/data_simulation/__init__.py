"""Stage Zero: synthetic ephemeral cloud/K8s telemetry generator + real-time replay.

Produces authentic-nested AWS CloudTrail, Kubernetes audit.k8s.io, and IdP/session
log streams (JSON Lines) with a separate ground-truth label sidecar, built
ground-truth-first so every downstream detection metric has honest labels to score against.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
