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

## Safety approach

- Public replies require a short-lived, single-use approval bound to the exact text and post.
- The original safety-gate demo also requires approval for refunds; deletion and unknown action types are blocked.
- OpenAI mode only generates drafts. The model has no tools and cannot approve or execute actions.
- The mock executor does not contact X/Twitter or a payment provider.
- The category and priority hints, approval identity, and executor are demo components; they are not production authentication or a trained risk classifier.

## Supporting evidence

The repository documents a command-line demo and unit tests for the safety gate. Run them from the repository root with:

    python -m safety_gate.demo
    python -m unittest safety_gate.test_gate safety_gate.test_workflow -v

The safety-gate documentation describes scenarios covering a human-approved mock reply and refund; missing, expired, altered, replayed, or unauthorized approvals; prompt injection attempting to trigger a refund or deletion; malformed refund requests; and unknown action types. It describes the expected behavior: valid approved actions are recorded by the mock executor, while unapproved or unsupported effects remain blocked. See `safety_gate/test_gate.py`, `safety_gate/test_workflow.py`, and [the safety-gate design README](safety_gate/README.md) for the documented coverage and demo details.

This section describes documented scenarios and expected behavior; it does not report a verified test run, pass count, or measured success rate.

## Limitations

- The response worker uses a deterministic mock responder by default. Optional OpenAI mode drafts text only; the safety-gate demo uses a deterministic agent stand-in.
- Category and priority hints are keyword-based. The older notebooks contain classification and RAG experiments, but they are not wired into the local pipeline.
- The demo operator is fixed and is not authenticated. Approval state and audit state are local and are not tamper-proof or durable production records.
- The safety gate controls authorization, not factual accuracy or reply quality. A human can still approve a bad reply.
- No live X/Twitter or payment provider is used. OpenAI is called only after explicit configuration, and post text is sent for draft generation.
- Production use would require authenticated approver identity, durable atomic approval-token consumption, tamper-evident audit storage, and enforcement that leaves no alternate path to external side effects.

Previously committed credentials have been revoked and are not used here.
