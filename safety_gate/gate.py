"""A small, fail-closed action gate for a customer-support agent prototype.

The module deliberately has no network client. All side effects in the demo go
through ``MockActionExecutor``. In a deployed system, the approval authority
must live behind an authenticated human interface that the model cannot call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import secrets
from typing import Any, Iterable, Mapping, Protocol


class ActionType(str, Enum):
    DRAFT_REPLY = "draft_reply"
    POST_PUBLIC_REPLY = "post_public_reply"
    ISSUE_REFUND = "issue_refund"
    DELETE_PUBLIC_POST = "delete_public_post"


class DecisionStatus(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class ExecutionStatus(str, Enum):
    EXECUTED = "executed"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ActionRequest:
    """Typed proposal from the agent; it is not itself permission to act."""

    action_id: str
    action_type: str
    requester: str
    target: str
    payload: Mapping[str, Any]
    untrusted_context: str = ""


@dataclass(frozen=True)
class PolicyDecision:
    status: DecisionStatus
    reason: str


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    action_id: str
    reason: str
    mock_result: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """Metadata-only audit record; customer text and approval tokens are omitted."""

    occurred_at: str
    event: str
    action_id: str
    action_type: str
    action_fingerprint: str
    actor: str
    reason: str


@dataclass(frozen=True)
class _ApprovalRecord:
    fingerprint: str
    approver: str
    issued_at: datetime
    expires_at: datetime


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def action_fingerprint(request: ActionRequest) -> str:
    """Hash all fields that determine what the agent is asking to do."""

    material = {
        "action_id": request.action_id,
        "action_type": request.action_type,
        "requester": request.requester,
        "target": request.target,
        "payload": request.payload,
        "untrusted_context": request.untrusted_context,
    }
    return hashlib.sha256(_canonical_json(material)).hexdigest()


class RiskPolicy:
    """Allow local drafts, require a human for public posts/refunds, deny the rest."""

    MAX_TEXT_LENGTH = 280
    MAX_REFUND_CENTS = 100_000
    MAX_PAYLOAD_BYTES = 8_000

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        if not isinstance(request, ActionRequest):
            return PolicyDecision(DecisionStatus.DENY, "request must use the ActionRequest schema")

        for field_name, value in (
            ("action_id", request.action_id),
            ("requester", request.requester),
            ("target", request.target),
            ("action_type", request.action_type),
        ):
            if not isinstance(value, str) or not value.strip():
                return PolicyDecision(DecisionStatus.DENY, f"{field_name} is required")
            if len(value) > 256:
                return PolicyDecision(DecisionStatus.DENY, f"{field_name} is too long")

        if not isinstance(request.payload, Mapping):
            return PolicyDecision(DecisionStatus.DENY, "payload must be a JSON object")
        if not isinstance(request.untrusted_context, str):
            return PolicyDecision(DecisionStatus.DENY, "untrusted_context must be text")

        try:
            payload_size = len(_canonical_json(request.payload))
        except (TypeError, ValueError, RecursionError):
            return PolicyDecision(DecisionStatus.DENY, "payload is not valid finite JSON")
        if payload_size > self.MAX_PAYLOAD_BYTES:
            return PolicyDecision(DecisionStatus.DENY, "payload exceeds the demo size limit")

        action_type = request.action_type
        if action_type == ActionType.DRAFT_REPLY.value:
            text = request.payload.get("text")
            if not isinstance(text, str) or not text.strip():
                return PolicyDecision(DecisionStatus.DENY, "draft text is required")
            if len(text) > self.MAX_TEXT_LENGTH:
                return PolicyDecision(DecisionStatus.DENY, "draft exceeds the demo platform limit")
            return PolicyDecision(DecisionStatus.ALLOW, "draft has no external side effect")

        if action_type == ActionType.POST_PUBLIC_REPLY.value:
            text = request.payload.get("text")
            if not isinstance(text, str) or not text.strip():
                return PolicyDecision(DecisionStatus.DENY, "public reply text is required")
            if len(text) > self.MAX_TEXT_LENGTH:
                return PolicyDecision(DecisionStatus.DENY, "reply exceeds the demo platform limit")
            return PolicyDecision(
                DecisionStatus.REQUIRE_APPROVAL,
                "public replies are externally visible and require human approval",
            )

        if action_type == ActionType.ISSUE_REFUND.value:
            amount_cents = request.payload.get("amount_cents")
            reason = request.payload.get("reason")
            if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
                return PolicyDecision(DecisionStatus.DENY, "refund amount must be integer cents")
            if amount_cents <= 0 or amount_cents > self.MAX_REFUND_CENTS:
                return PolicyDecision(DecisionStatus.DENY, "refund amount is outside the demo policy limit")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 250:
                return PolicyDecision(DecisionStatus.DENY, "a short refund reason is required")
            return PolicyDecision(
                DecisionStatus.REQUIRE_APPROVAL,
                "financial actions require human approval",
            )

        # Deletion and unknown action types are not exposed by this prototype.
        return PolicyDecision(DecisionStatus.DENY, "action type is unsupported by the allowlist")


class ApprovalError(ValueError):
    """Raised when the trusted approval console cannot grant an approval."""


class ApprovalAuthority:
    """In-memory stand-in for a separate authenticated human approval service.

    ``approver_id`` must come from a trusted identity provider in production.
    Do not expose this method as an agent tool or accept model-supplied identity.
    """

    def __init__(
        self,
        authorized_approvers: Iterable[str],
        policy: RiskPolicy | None = None,
        ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._authorized_approvers = {name for name in authorized_approvers if name}
        self._policy = policy or RiskPolicy()
        self._ttl = ttl
        self._records: dict[str, _ApprovalRecord] = {}
        self._consumed: set[str] = set()
        self.audit_events: list[AuditEvent] = []

    def approve(
        self,
        request: ActionRequest,
        approver_id: str,
        *,
        now: datetime | None = None,
    ) -> str:
        decision = self._policy.evaluate(request)
        if decision.status is not DecisionStatus.REQUIRE_APPROVAL:
            raise ApprovalError("policy does not permit this action to be approved")
        if not isinstance(approver_id, str) or not approver_id:
            raise ApprovalError("approver identity is invalid")
        if approver_id not in self._authorized_approvers:
            raise ApprovalError("approver is not authorized")
        if approver_id == request.requester:
            raise ApprovalError("requester cannot approve their own action")
        if self._ttl <= timedelta(0):
            raise ApprovalError("approval lifetime must be positive")

        issued_at = _utc(now)
        fingerprint = action_fingerprint(request)
        token = secrets.token_urlsafe(32)
        expires_at = issued_at + self._ttl
        self._records[token] = _ApprovalRecord(
            fingerprint=fingerprint,
            approver=approver_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        self.audit_events.append(
            AuditEvent(
                occurred_at=issued_at.isoformat(),
                event="approval_granted",
                action_id=request.action_id,
                action_type=request.action_type,
                action_fingerprint=fingerprint,
                actor=approver_id,
                reason="approval bound to the exact action proposal",
            )
        )
        return token

    def consume(
        self,
        token: str | None,
        request: ActionRequest,
        *,
        now: datetime | None = None,
    ) -> tuple[_ApprovalRecord | None, str | None]:
        if not isinstance(token, str) or not token or token not in self._records:
            return None, "approval token is missing or unknown"
        if token in self._consumed:
            return None, "approval token has already been used"

        record = self._records[token]
        current_time = _utc(now)
        if current_time >= record.expires_at:
            return None, "approval has expired"
        if action_fingerprint(request) != record.fingerprint:
            return None, "approval does not match this exact action"

        # Consume before calling an external adapter. If an outcome is uncertain,
        # the action needs a fresh approval instead of risking a duplicate effect.
        self._consumed.add(token)
        return record, None


class ActionExecutor(Protocol):
    def execute(self, request: ActionRequest, idempotency_key: str) -> str:
        """Perform one action and return a short receipt."""


class MockActionExecutor:
    """A safe executor for the demo; it records actions and never contacts services."""

    def __init__(self) -> None:
        self.executed: list[ActionRequest] = []
        self.drafts: list[ActionRequest] = []
        self.public_replies: list[ActionRequest] = []
        self.refunds: list[ActionRequest] = []
        self._fingerprints: dict[str, str] = {}

    def execute(self, request: ActionRequest, idempotency_key: str) -> str:
        fingerprint = action_fingerprint(request)
        previous = self._fingerprints.get(idempotency_key)
        if previous is not None:
            if previous != fingerprint:
                raise RuntimeError("idempotency key reused for a different action")
            return f"duplicate suppressed: {idempotency_key}"
        self._fingerprints[idempotency_key] = fingerprint
        self.executed.append(request)
        if request.action_type == ActionType.DRAFT_REPLY.value:
            self.drafts.append(request)
        elif request.action_type == ActionType.POST_PUBLIC_REPLY.value:
            self.public_replies.append(request)
        elif request.action_type == ActionType.ISSUE_REFUND.value:
            self.refunds.append(request)
        return f"mock receipt {idempotency_key}"


class ActionBroker:
    """The only route from agent proposals to the configured executor."""

    def __init__(
        self,
        executor: ActionExecutor,
        approvals: ApprovalAuthority,
        policy: RiskPolicy | None = None,
    ) -> None:
        self._executor = executor
        self._approvals = approvals
        self._policy = policy or RiskPolicy()
        self._seen_actions: dict[str, str] = {}
        self._executed_actions: set[str] = set()
        self.audit_events: list[AuditEvent] = []

    def execute(
        self,
        request: ActionRequest,
        approval_token: str | None = None,
        *,
        now: datetime | None = None,
    ) -> ExecutionResult:
        decision = self._policy.evaluate(request)
        try:
            fingerprint = action_fingerprint(request)
        except (AttributeError, TypeError, ValueError, RecursionError):
            return ExecutionResult(
                ExecutionStatus.BLOCKED,
                getattr(request, "action_id", "unknown"),
                "malformed request could not be fingerprinted",
            )

        action_id = request.action_id
        if decision.status is DecisionStatus.DENY:
            self._record("action_blocked", request, fingerprint, request.requester, decision.reason, now)
            return ExecutionResult(ExecutionStatus.BLOCKED, action_id, decision.reason)

        previous_fingerprint = self._seen_actions.get(action_id)
        if previous_fingerprint is not None and previous_fingerprint != fingerprint:
            reason = "action ID was reused with different content"
            self._record("action_blocked", request, fingerprint, request.requester, reason, now)
            return ExecutionResult(ExecutionStatus.BLOCKED, action_id, reason)
        self._seen_actions[action_id] = fingerprint

        if action_id in self._executed_actions:
            reason = "action ID has already executed"
            self._record("action_blocked", request, fingerprint, request.requester, reason, now)
            return ExecutionResult(ExecutionStatus.BLOCKED, action_id, reason)

        approval_record: _ApprovalRecord | None = None
        if decision.status is DecisionStatus.REQUIRE_APPROVAL:
            if approval_token is None:
                self._record(
                    "approval_required", request, fingerprint, request.requester, decision.reason, now
                )
                return ExecutionResult(ExecutionStatus.APPROVAL_REQUIRED, action_id, decision.reason)
            approval_record, error = self._approvals.consume(
                approval_token, request, now=now
            )
            if error is not None or approval_record is None:
                reason = error or "approval could not be verified"
                self._record("action_blocked", request, fingerprint, request.requester, reason, now)
                return ExecutionResult(ExecutionStatus.BLOCKED, action_id, reason)
            self._record(
                "approval_consumed",
                request,
                fingerprint,
                approval_record.approver,
                "single-use approval verified",
                now,
            )
        elif approval_token is not None:
            reason = "approval token supplied for an action that does not require it"
            self._record("action_blocked", request, fingerprint, request.requester, reason, now)
            return ExecutionResult(ExecutionStatus.BLOCKED, action_id, reason)

        try:
            receipt = self._executor.execute(request, idempotency_key=action_id)
        except Exception as exc:  # fail closed; do not retry an uncertain side effect
            reason = f"executor failed ({type(exc).__name__}); fresh review is required"
            self._record("execution_failed", request, fingerprint, request.requester, reason, now)
            return ExecutionResult(ExecutionStatus.FAILED, action_id, reason)

        self._executed_actions.add(action_id)
        self._record("action_executed", request, fingerprint, request.requester, "mock executor only", now)
        return ExecutionResult(ExecutionStatus.EXECUTED, action_id, "action completed", receipt)

    def _record(
        self,
        event: str,
        request: ActionRequest,
        fingerprint: str,
        actor: str,
        reason: str,
        now: datetime | None,
    ) -> None:
        self.audit_events.append(
            AuditEvent(
                occurred_at=_utc(now).isoformat(),
                event=event,
                action_id=request.action_id,
                action_type=request.action_type,
                action_fingerprint=fingerprint,
                actor=actor,
                reason=reason,
            )
        )
