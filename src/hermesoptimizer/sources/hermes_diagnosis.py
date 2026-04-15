"""
Phase 1 unified diagnosis model for Hermes.

Provides:
- Diagnosis: enriched Finding wrapper with phase, root_cause, remediation hints
- diagnose(): single entry point that takes a Finding and returns a Diagnosis
- Severity and confidence constants for consistent classification
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from hermesoptimizer.catalog import Finding


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiagnosisKind(str, Enum):
    CONFIG_MISSING_FIELD = "config-missing-field"
    CONFIG_STALE_PROVIDER = "config-stale-provider"
    CONFIG_BAD_ENDPOINT = "config-bad-endpoint"
    SESSION_ERROR = "session-error"
    SESSION_TIMEOUT = "session-timeout"
    SESSION_CRASH = "session-crash"
    SESSION_RETRY = "session-retry"
    LOG_AUTH_FAILURE = "log-auth-failure"
    LOG_PROVIDER_FAILURE = "log-provider-failure"
    LOG_RUNTIME_FAILURE = "log-runtime-failure"
    GATEWAY_DOWN = "gateway-down"
    GATEWAY_UNHEALTHY = "gateway-unhealthy"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Diagnosis dataclass
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Diagnosis:
    """
    Phase 1 enriched finding.

    Wraps a Finding with additional classification metadata:
    - phase: always "phase1"
    - root_cause: category string describing the underlying cause
    - remediation: short suggested fix (may be None)
    - kind: one of DiagnosisKind values
    - severity: Severity enum value
    - confidence: Confidence enum value
    """

    finding: Finding
    phase: str = "phase1"
    root_cause: str | None = None
    remediation: str | None = None
    kind: str | None = None

    @property
    def severity(self) -> str:
        return self.finding.severity

    @property
    def confidence(self) -> str:
        return self.finding.confidence or "low"

    @property
    def router_note(self) -> str | None:
        return self.finding.router_note

    def to_finding(self) -> Finding:
        """Return the underlying Finding (for loop compatibility)."""
        return self.finding


# ---------------------------------------------------------------------------
# Diagnosis constants for mapping
# ---------------------------------------------------------------------------

# Category -> (kind, severity, confidence, root_cause, remediation)
_DIAGNOSIS_MAP: dict[str, tuple[str, str, str, str | None, str | None]] = {
    "config-missing-field":    (DiagnosisKind.CONFIG_MISSING_FIELD,  Severity.HIGH,   Confidence.HIGH,   "missing-required-config-field",          "add missing field to config.yaml"),
    "config-stale-provider":    (DiagnosisKind.CONFIG_STALE_PROVIDER,  Severity.MEDIUM, Confidence.MEDIUM, "stale-or-unknown-provider-name",        "verify provider name is correct"),
    "config-bad-endpoint":      (DiagnosisKind.CONFIG_BAD_ENDPOINT,    Severity.HIGH,   Confidence.HIGH,   "malformed-or-insecure-endpoint-url",     "fix base_url to use https and correct format"),
    "session-error":            (DiagnosisKind.SESSION_ERROR,          Severity.MEDIUM, Confidence.HIGH,   "provider-returned-error-status",         "check provider API key and quota"),
    "session-timeout":          (DiagnosisKind.SESSION_TIMEOUT,         Severity.HIGH,   Confidence.HIGH,   "request-timed-out",                       "increase timeout or check provider latency"),
    "session-crash":            (DiagnosisKind.SESSION_CRASH,          Severity.CRITICAL, Confidence.MEDIUM, "worker-process-crashed",                  "review worker logs for root cause"),
    "session-retry":            (DiagnosisKind.SESSION_RETRY,          Severity.LOW,    Confidence.HIGH,   "request-was-retried",                     "investigate transient provider issues"),
    "log-auth-failure":         (DiagnosisKind.LOG_AUTH_FAILURE,       Severity.HIGH,   Confidence.HIGH,   "authentication-failed",                    "verify API key env var and permissions"),
    "log-provider-failure":     (DiagnosisKind.LOG_PROVIDER_FAILURE,   Severity.MEDIUM, Confidence.HIGH,   "provider-returned-error",                 "check provider status and logs"),
    "log-runtime-failure":      (DiagnosisKind.LOG_RUNTIME_FAILURE,    Severity.MEDIUM, Confidence.MEDIUM, "runtime-exception",                       "review exception stack trace"),
    "gateway-down":             (DiagnosisKind.GATEWAY_DOWN,           Severity.CRITICAL, Confidence.HIGH, "gateway-not-responding",                  "start the Hermes gateway service"),
    "gateway-unhealthy":        (DiagnosisKind.GATEWAY_UNHEALTHY,      Severity.HIGH,   Confidence.MEDIUM, "gateway-health-check-failed",             "check gateway /health endpoint"),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def diagnose(finding: Finding) -> Diagnosis:
    """
    Enrich a Finding with Phase 1 diagnosis metadata.

    Returns a Diagnosis with kind, severity, confidence, root_cause,
    and remediation populated from the internal map.
    """
    kind = finding.kind or "unknown"
    severity = finding.severity or Severity.MEDIUM
    confidence = finding.confidence or Confidence.LOW

    mapped = _DIAGNOSIS_MAP.get(kind)
    if mapped:
        diag_kind, diag_sev, diag_conf, root_cause, remediation = mapped
        # Upgrade to the mapped classification when it is more specific.
        if _severity_order(severity) > _severity_order(diag_sev):
            severity = diag_sev
        if _confidence_order(confidence) > _confidence_order(diag_conf):
            confidence = diag_conf
        kind = diag_kind.value if isinstance(diag_kind, DiagnosisKind) else str(diag_kind)
        severity = diag_sev.value if isinstance(diag_sev, Severity) else str(diag_sev)
        confidence = diag_conf.value if isinstance(diag_conf, Confidence) else str(diag_conf)
    else:
        root_cause = None
        remediation = None
        kind = str(kind)
        severity = str(severity)
        confidence = str(confidence)

    diag = Diagnosis(
        finding=finding,
        root_cause=root_cause,
        remediation=remediation,
        kind=kind,
    )
    # Sync severity/confidence back to finding
    finding.severity = severity
    finding.confidence = confidence
    finding.router_note = f"[phase1:{kind}] {finding.router_note or ''}".strip()
    return diag


def _severity_order(s: str) -> int:
    order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    return order.get(s, 99)


def _confidence_order(c: str) -> int:
    order = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
    return order.get(c, 99)


def diagnose_all(findings: list[Finding]) -> list[Diagnosis]:
    """Diagnose a list of findings."""
    return [diagnose(f) for f in findings]
