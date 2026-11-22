# ReplyGuard: Social-Care Safety Demo

## Project overview

ReplyGuard is a local prototype for reviewing AI-assisted replies in a social-care workflow. It addresses the risk that a support agent could publish an unauthorized public reply or take another consequential action before a person reviews it. The demo includes a mock Twitter composer and a social-care console. Posts can pass through Kafka, local SQLite, and a response queue; approved replies are recorded only by a mock executor.

## Run the full local pipeline

Use Python 3.10 or newer and Docker Desktop. From the repository root:

On Windows PowerShell, create the virtual environment and install dependencies without activating it (this avoids PowerShell script-policy changes):

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-pipeline.txt
    docker compose up -d kafka

In separate terminals, run the workers using the virtual-environment Python:

    .\.venv\Scripts\python.exe -m replyguard_pipeline.ingest_worker
    .\.venv\Scripts\python.exe -m replyguard_pipeline.response_worker

Then run both Streamlit apps in separate terminals:

    .\.venv\Scripts\streamlit.exe run mock_twitter_app.py --server.port 8501
    .\.venv\Scripts\streamlit.exe run app.py --server.port 8502

Open http://localhost:8501 for Mock Twitter and http://localhost:8502 for the manager console. The console refreshes the Kafka inbox every five seconds. The SQLite database is created at data/replyguard.sqlite3 and is ignored by Git.

## Message flow

1. Mock Twitter publishes a sample post to the local Kafka incoming topic.
2. The ingest worker saves the post to SQLite and publishes a response request to a second Kafka topic.
3. The response worker creates a draft and stores it in SQLite.
4. The manager console displays the post and draft. A reviewer can edit, approve, or reject it.
5. Approval passes through the safety gate and records a mock post; it never contacts X/Twitter.

The default responder is deterministic and free. To use OpenAI, install the optional SDK with:

    .\.venv\Scripts\python.exe -m pip install -r .\requirements-openai.txt

Then open the manager console sidebar, enter an OpenAI model ID and API key, and save the settings. The key is stored in the operating-system credential store (Windows Credential Manager on Windows), not in the project database or Git. The response worker checks these settings for every queued post, so you do not need to restart it after saving. The default model field is prefilled with `gpt-6-luna`; you can change it if your API account uses a different model.

OpenAI mode is opt-in. Each queued or retried post can make a paid API call, and the post text is sent to OpenAI for draft generation. The model has no tools and cannot approve or post anything. Responses are accepted only when the API reports completion and the draft ends with punctuation; incomplete drafts are marked failed instead of entering review. Clear the saved settings in the manager sidebar to return to the free mock responder. Environment-variable configuration remains supported for terminal-only use.

## Risk-aware triage recommender (experimental branch)

This branch adds a transparent triage aid to the Kafka inbox. It recommends which posts a social-media manager should inspect first, using four visible signals:

- **Severity wording (40%)** — configured phrases for possible safety, security, privacy, fraud, payment, or service issues.
- **Explicit urgency (25%)** — phrases such as “right now,” “today,” or “before my flight.”
- **Potential reach (25%)** — a follower-count proxy entered in Mock Twitter.
- **Recent attention (10%)** — synthetic engagements in the last hour.

The manager inbox sorts posts by score and shows a priority band, the component values, and the matched reasons. A configured severe-harm/security signal has a score floor so that a low-reach account cannot bury a potentially serious report. The bands are **Urgent** (score 78+, or the severe-signal floor), **High** (score 58+ or high-severity wording), **Elevated** (score 35+), and **Routine** (below 35).

Reach and engagement values are optional synthetic demo inputs; the app does not fetch social-media data. Existing database rows and tweets without these fields are treated as having unknown reach and no recent activity. The SQLite setup adds the new columns automatically while retaining existing rows.

This is a review-order recommendation only. It does not approve, reject, or publish a reply, and it does not currently stop routine or unrelated posts from entering the existing draft-generation queue. The normal human approval gate still applies to every public reply.

### Triage limitations

The prototype uses fixed English phrase lists and simple score weights, not a trained classifier or validated impact model. It can miss sarcasm, indirect language, new terms, and non-English posts, and can overreact to phrases used figuratively or in a negated sentence. Follower count and recent engagement are rough visibility proxies; they do not establish credibility, harm, or importance. The weights and thresholds need evaluation against labeled examples and review by social-care operators before any real use.

## Safety approach

- Public replies require a short-lived, single-use approval bound to the exact text and post.
- The original safety-gate demo also requires approval for refunds; deletion and unknown action types are blocked.
- OpenAI mode only generates drafts. The model has no tools and cannot approve or execute actions.
- The mock executor does not contact X/Twitter or a payment provider.
- The category and priority hints, approval identity, and executor are demo components; they are not production authentication or a trained risk classifier.

## Supporting evidence

The social-care console includes a **Safety test lab** tab. Start the app, open that tab, then choose **Run all 13 safety tests** or expand an individual test and click **Run this test**. The app displays the actual pass/fail/error counts and the Python unittest output from that run. Results are not prefilled.

The test cases instantiate fresh in-memory approval/workflow objects and use `MockActionExecutor`. Running them does not contact X/Twitter, OpenAI, Kafka, or a payment provider, and does not modify the Kafka pipeline's SQLite records. They test the gate and simulated workflow; they do not test production authentication or whether generated replies are factually correct.

You can also run the same tests from the repository root:

    python -m safety_gate.demo
    python -m unittest safety_gate.test_gate safety_gate.test_workflow -v

### What the 13 tests check

1. `test_local_draft_executes_without_approval` — A local draft is recorded without approval because it has no external effect.
2. `test_public_post_is_held_without_approval` — A public reply without approval remains pending and is not recorded by the executor.
3. `test_approved_exact_action_executes_once` — A matching approval permits one execution; replaying its token is blocked, and audit events omit reply text.
4. `test_changed_payload_cannot_use_old_approval` — Editing the reply after approval invalidates that approval.
5. `test_expired_approval_fails_closed` — An approval used at its five-minute expiry boundary is rejected.
6. `test_unauthorized_and_self_approval_are_rejected` — An unknown operator and the requester themselves cannot approve the action.
7. `test_unsupported_delete_is_denied_even_if_approval_is_attempted` — Deletion is outside the allowlist and stays blocked even if approval is requested.
8. `test_prompt_injection_in_context_does_not_grant_approval` — Customer text claiming a refund is approved cannot grant authorization.
9. `test_malformed_refund_is_denied` — A refund amount supplied as text instead of integer cents is rejected.
10. `test_unknown_action_is_denied_by_default` — An unsupported action such as `send_email` is blocked.
11. `test_delivery_case_requires_approval_before_public_reply` — A delivery reply is drafted locally, held for review, and recorded once only after approval.
12. `test_refund_is_mocked_and_runs_only_after_human_approval` — No refund is recorded before review; approval records one mock refund.
13. `test_injection_cannot_approve_refund_or_enable_delete` — A malicious request leaves reply/refund pending, blocks deletion, and records no public reply or refund.

These descriptions explain the assertions covered by the suite. The recorded result below reflects one local run, not a guarantee for future code revisions.

### Recorded run

- 2026-11-17: 13 of 13 tests passed in the app's Safety test lab.

## Demo video

[Watch the ReplyGuard demo](https://youtu.be/akQFezkyAmc?si=n5SqDZ1iCSUlt8LF)

## Limitations

- The response worker uses a deterministic mock responder by default. Optional OpenAI mode drafts text only; the safety-gate demo uses a deterministic agent stand-in.
- Category and priority hints are keyword-based. The older notebooks contain classification and RAG experiments, but they are not wired into the local pipeline.
- The demo operator is fixed and is not authenticated. Approval state and audit state are local and are not tamper-proof or durable production records.
- The safety gate controls authorization, not factual accuracy or reply quality. A human can still approve a bad reply.
- The experimental triage branch uses an unvalidated phrase-based score and synthetic audience signals. It only sorts the manager queue; every post still enters the draft-generation path.
- No live X/Twitter or payment provider is used. OpenAI is called only after explicit configuration, and post text is sent for draft generation.
- Production use would require authenticated approver identity, durable atomic approval-token consumption, tamper-evident audit storage, and enforcement that leaves no alternate path to external side effects.

Previously committed credentials have been revoked and are not used here.
