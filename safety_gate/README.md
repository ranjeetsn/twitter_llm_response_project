# Human approval gate for high-impact support actions

This prototype adapts the repository's customer-support agent to the Drawerrr AI Safety Challenge. It demonstrates a narrow safety boundary around actions that could have an external effect: publishing a customer reply and issuing a refund.

## Run the demo

From the repository root, using Python 3.10 or newer:

```bash
python -m safety_gate.demo
python -m unittest safety_gate.test_gate -v
```

The demo uses only `MockActionExecutor`. It does not connect to X/Twitter, a payment processor, Kafka, or an LLM.

## How the gate works

1. The agent submits a typed `ActionRequest`; the request is a proposal, not authority to act.
2. `RiskPolicy` allows a local draft, requires a human approval for public replies and refunds, and denies unsupported or malformed actions.
3. The human approval authority issues a short-lived, single-use token bound to a SHA-256 fingerprint of the entire proposal, including the target, payload, requester, and untrusted context.
4. `ActionBroker` checks the policy again, verifies the fingerprint and expiry, consumes the token before execution, and blocks duplicate action IDs.
5. Only the broker can call the configured executor. The included executor is a mock and records the action instead of contacting a service.

The action policy does not treat text in a customer message as an approval instruction. Prompt injection in the untrusted context cannot satisfy the separate approval check.

## Controls shown

- Default deny for unknown action types and invalid fields.
- Human review for every public post and refund.
- Approval bound to the exact action content and destination.
- Five-minute approval expiry and one-time token use.
- Duplicate action-ID protection and an idempotency key passed to the executor.
- Metadata-only audit events; the proposal text and approval token are not copied into the audit log.
- No real-world API credentials or external action adapter in the demo.

## Test coverage

The unit tests cover a safe local draft, an unapproved public post, a successful approval, replay, changed content, expiry, unauthorized/self-approval, prompt injection, malformed refund data, and an unsupported delete action.

## Security boundary and limitations

This is a reproducible prototype, not a production authorization service. The demo passes an approver ID directly to `ApprovalAuthority`; a deployed system must derive identity from an authenticated human session and must never expose the approval method as an agent tool. The approval ledger and audit events are in memory, so production needs durable storage, atomic single-use consumption, tamper-evident audit retention, and downstream idempotency. The mock executor cannot prove the behavior of a live provider. The gate controls whether a typed action can execute; it does not determine whether the proposed message is truthful, appropriate, or harmless after a human approves it.

For a live integration, enforce this gate at the tool/API boundary so no alternate code path can publish, refund, or delete directly. Keep real credentials in a secret manager, rotate exposed credentials, and test the provider's idempotency and failure semantics before enabling execution.
