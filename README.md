# ReplyGuard: Social-Care Safety Demo

ReplyGuard has two local Streamlit apps: a tiny mock Twitter composer and a social-care console. A post can move through Kafka, be stored in a local SQLite database, receive a suggested response, and wait for human review. Approved replies are recorded only by a mock executor.

## Run the full local pipeline

Use Python 3.10 or newer and Docker Desktop. From the repository root:

    pip install -r requirements-pipeline.txt
    docker compose up -d kafka

In separate terminals, start the two workers:

    python -m replyguard_pipeline.ingest_worker
    python -m replyguard_pipeline.response_worker

Then run both Streamlit apps in separate terminals:

    streamlit run mock_twitter_app.py --server.port 8501
    streamlit run app.py --server.port 8502

Open http://localhost:8501 for Mock Twitter and http://localhost:8502 for the manager console. The console refreshes the Kafka inbox every five seconds. The SQLite database is created at data/replyguard.sqlite3 and is ignored by Git.

## Message flow

1. Mock Twitter publishes a sample post to the local Kafka incoming topic.
2. The ingest worker saves the post to SQLite and publishes a response request to a second Kafka topic.
3. The response worker creates a draft and stores it in SQLite.
4. The manager console displays the post and draft. A reviewer can edit, approve, or reject it.
5. Approval passes through the safety gate and records a mock post; it never contacts X/Twitter.

The default responder is deterministic and free. To enable the optional OpenAI provider, install requirements-openai.txt, set REPLYGUARD_LLM_PROVIDER=openai, OPENAI_API_KEY, and REPLYGUARD_OPENAI_MODEL in the response-worker environment, then start or restart that worker. Each queued post may then incur an API charge and its text is sent to OpenAI. Retrying a failed response can make another call.

## Safety controls and limits

- Public replies require a short-lived, single-use approval bound to the exact text and post.
- Refunds in the original safety demo also require approval; deletion and unknown actions are blocked.
- The agent, category and priority hints, OpenAI-free responder, approval identity, and executor are demo components.
- The demo operator is fixed and is not authentication. SQLite is local, but audit state and production protections are not tamper-proof.
- No live X/Twitter, payment, or Kafka cloud service is used. Kafka runs locally in Docker; the database stays on this computer.

Run the original safety-gate demo and unit tests with:

    python -m safety_gate.demo
    python -m unittest safety_gate.test_gate safety_gate.test_workflow -v

See safety_gate/README.md for the safety-gate design, evidence, and production limitations. The older notebooks contain experiments for tweet classification, RAG, call transcription, and social streaming; they are not wired into the new local pipeline. Previously committed credentials have been revoked and are not used here.
