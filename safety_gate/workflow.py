"""End-to-end, deterministic simulation of a support agent behind ActionBroker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from safety_gate.gate import (
    ActionBroker,
    ActionRequest,
    ActionType,
    ApprovalAuthority,
    ExecutionResult,
)


@dataclass(frozen=True)
class SupportCase:
    case_id: str
    customer_message: str


@dataclass(frozen=True)
class AgentPlan:
    draft: ActionRequest
    external_actions: tuple[ActionRequest, ...]


@dataclass(frozen=True)
class ActionAttempt:
    request: ActionRequest
    result: ExecutionResult


@dataclass(frozen=True)
class WorkflowRun:
    case: SupportCase
    plan: AgentPlan
    draft_result: ExecutionResult
    action_attempts: tuple[ActionAttempt, ...]


class DeterministicSupportAgent:
    """Free stand-in for the original LLM step; deliberately uses no model API."""

    REFUND_CUES = ("refund", "charged twice", "duplicate charge", "double charged")
    DELETE_CUES = ("delete the complaint", "remove the complaint", "delete my post")

    def propose(self, case: SupportCase) -> AgentPlan:
        if not case.case_id.strip() or not case.customer_message.strip():
            raise ValueError("case ID and customer message are required")

        message = case.customer_message.lower()
        requests_refund = any(cue in message for cue in self.REFUND_CUES)
        reply_text = (
            "I’m sorry about the billing issue. A support lead will review your case."
            if requests_refund
            else "Thanks for letting us know. A support lead will review your case."
        )

        draft = ActionRequest(
            action_id=f"{case.case_id}:draft",
            action_type=ActionType.DRAFT_REPLY.value,
            requester="support-agent",
            target=case.case_id,
            payload={"text": reply_text},
            untrusted_context=case.customer_message,
        )
        actions = [
            ActionRequest(
                action_id=f"{case.case_id}:public-reply",
                action_type=ActionType.POST_PUBLIC_REPLY.value,
                requester="support-agent",
                target=case.case_id,
                payload={"text": reply_text},
                untrusted_context=case.customer_message,
            )
        ]

        if requests_refund:
            actions.append(
                ActionRequest(
                    action_id=f"{case.case_id}:refund",
                    action_type=ActionType.ISSUE_REFUND.value,
                    requester="support-agent",
                    target=case.case_id,
                    payload={
                        "amount_cents": 2_500,
                        "reason": "simulated duplicate-charge request",
                    },
                    untrusted_context=case.customer_message,
                )
            )

        if any(cue in message for cue in self.DELETE_CUES):
            actions.append(
                ActionRequest(
                    action_id=f"{case.case_id}:delete",
                    action_type=ActionType.DELETE_PUBLIC_POST.value,
                    requester="support-agent",
                    target=case.case_id,
                    payload={"reason": "customer text requested removal"},
                    untrusted_context=case.customer_message,
                )
            )

        return AgentPlan(draft=draft, external_actions=tuple(actions))


class SupportWorkflow:
    """Runs intake, deterministic proposal, policy checks, and mock execution."""

    def __init__(
        self,
        broker: ActionBroker,
        approvals: ApprovalAuthority,
        agent: DeterministicSupportAgent | None = None,
    ) -> None:
        self._broker = broker
        self._approvals = approvals
        self._agent = agent or DeterministicSupportAgent()

    def start_case(self, case: SupportCase, *, now: datetime | None = None) -> WorkflowRun:
        plan = self._agent.propose(case)
        draft_result = self._broker.execute(plan.draft, now=now)
        attempts = tuple(
            ActionAttempt(
                request=request,
                result=self._broker.execute(request, now=now),
            )
            for request in plan.external_actions
        )
        return WorkflowRun(case, plan, draft_result, attempts)

    def approve_and_execute(
        self,
        run: WorkflowRun,
        action_id: str,
        approver_id: str,
        *,
        now: datetime | None = None,
    ) -> ExecutionResult:
        request = next(
            (item for item in run.plan.external_actions if item.action_id == action_id),
            None,
        )
        if request is None:
            raise ValueError("action is not part of this workflow run")
        approval = self._approvals.approve(request, approver_id, now=now)
        return self._broker.execute(request, approval_token=approval, now=now)
