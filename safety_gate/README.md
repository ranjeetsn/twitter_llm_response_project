# ReplyGuard: mock end-to-end safety for support agents

ReplyGuard demonstrates how to keep an AI customer-support workflow from publishing a public reply or issuing a refund without human authorization. It runs the safety-relevant path from an incoming complaint, through a simulated agent proposal and policy gate, to mock execution and audit events.

The repository also includes a separate local Kafka/SQLite pipeline with two Streamlit apps. Follow the root README to run Mock Twitter, the ingest and response workers, and the manager console together. The manager console's Kafka inbox uses this same approval gate before recording a mock public reply.

## Is a simulation suitable for the challenge?

Yes. The [challenge guide](https://www.drawerrr.com/challenge/ai-safety-and-control/prevent-irreversible-autonomous-actions) recommends a mock API or sandbox for the test environment and welcomes prototypes when implementation, evidence, and limitations are explained honestly. A simulation also avoids paid model calls and real posts or payments. It is important to describe it as a tested prototype, not a production deployment.

The safety evidence is focused on the challenge's core question: does the action boundary stop a risky effect when approval is absent, expired, unauthorized, or bound to different content? The tests exercise those paths alongside prompt injection, malformed refund values, replay, and unsupported deletion.

## Run it

From the repository root with Python 3.10 or newer:

```bash
pip install -r requirements-demo.txt
streamlit run app.py
```

The dashboard opens a social-care inbox with sample cases, manual message entry, and CSV import. Reviewers can approve or reject proposed actions, then inspect mock outcomes and export the activity log. All app state is session-local.

For the command-line safety demo and tests:

```bash
python -m safety_gate.demo
python -m unittest safety_gate.test_gate safety_gate.test_workflow -v
```

Both commands use only the Python standard library. They do not call the paid LLM, X/Twitter, Kafka, or a payment provider.

## End-to-end flow

1. A sample support case enters the simulator.
2. A deterministic agent stand-in creates a local draft and proposes external actions. Keyword rules make the examples repeatable; this is not a live LLM.
3. `RiskPolicy` allows the local draft, holds public replies and refunds for approval, and denies deletion or unknown action types.
4. A separate approval authority issues a five-minute, single-use token bound to the exact action fingerprint.
5. `ActionBroker` rechecks policy, expiry, fingerprint, action ID, and token use before calling the mock executor.
6. The mock executor records posts/refunds in local lists. Audit events record decision metadata without storing customer text or approval tokens.

The demo completes one human-approved public reply and one human-approved refund. A prompt-injection case asks the agent to refund and delete a complaint; the refund and public reply stay pending, and deletion is blocked.

## Safety controls

- Default deny for malformed requests and action types outside the allowlist.
- Human approval for every public reply and refund.
- Approval expires after five minutes and cannot be reused.
- The approval is bound to the target, content, requester, action ID, and untrusted customer context.
- The action ID cannot be reused with altered content; the executor receives it as an idempotency key.
- Untrusted customer text cannot itself grant approval.
- The executor is mock-only; no credentials or live service adapters are included.

## Tests

The gate tests cover drafts, missing approval, exact-action approval, changed content, expiry, replay, unauthorized/self-approval, prompt injection, malformed refunds, unknown actions, and deletion. Workflow tests cover intake-to-approved-post, approval-gated refund execution, and a prompt-injection request that cannot authorize a refund or deletion.

## Limits and production requirements

The simulation covers the safety-relevant flow, not the repository's legacy Kafka stream or a paid LLM call. The agent is deterministic so the demo is cheap and reproducible. The in-memory approval ledger and audit log are not durable. The demo passes an approver ID directly; production must derive identity from an authenticated operator session and must not expose the approval method as an agent tool. A production deployment also needs atomic persistent token consumption, tamper-evident audit storage, API-level enforcement with no alternate path to side effects, and provider idempotency. Human approval can still approve bad content; the gate controls authorization, not truthfulness or quality.

Previously committed credentials have been revoked. The demo uses no API credentials, and its code does not call external services.

## Short submission description

ReplyGuard is a mock end-to-end customer-support agent safety demo. It allows a draft to remain local, requires a short-lived human approval tied to the exact proposed action before a public reply or refund, and blocks unsupported actions. A deterministic agent, mock publisher, mock refund ledger, audit events, and adversarial tests make the control path reproducible without paid model calls or live external actions. The prototype documents its identity, persistence, and deployment limits.
