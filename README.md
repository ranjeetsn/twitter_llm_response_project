# ReplyGuard: Social-Care Safety Demo

ReplyGuard has two local Streamlit apps: a tiny mock Twitter composer and a social-care console. A post can move through Kafka, be stored in a local SQLite database, receive a suggested response, and wait for human review. Approved replies are recorded only by a mock executor.

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

OpenAI mode is opt-in. Each queued or retried post can make a paid API call, and the post text is sent to OpenAI for draft generation. The model has no tools and cannot approve or post anything. Clear the saved settings in the manager sidebar to return to the free mock responder. Environment-variable configuration remains supported for terminal-only use.

## Safety controls and limits

- Public replies require a short-lived, single-use approval bound to the exact text and post.
- Refunds in the original safety demo also require approval; deletion and unknown actions are blocked.
- The mock responder, keyword-based category and priority hints, approval identity, and executor are demo components. OpenAI mode is optional and drafts text only.
- The demo operator is fixed and is not authentication. SQLite is local, but audit state and production protections are not tamper-proof.
- No live X/Twitter or payment provider is used. Kafka runs locally in Docker; the database stays on this computer. OpenAI is called only after explicit configuration for text drafts.

Run the original safety-gate demo and unit tests with:

    python -m safety_gate.demo
    python -m unittest safety_gate.test_gate safety_gate.test_workflow -v

See safety_gate/README.md for the safety-gate design, evidence, and production limitations. The older notebooks contain experiments for tweet classification, RAG, call transcription, and social streaming; they are not wired into the new local pipeline. Previously committed credentials have been revoked and are not used here.
