# ReplyGuard: AI Support Safety Console

ReplyGuard is a local Streamlit demo for handling customer posts like a social-care team: review an inbox, triage cases, inspect proposed replies and refunds, make a human decision, and track the mock outcome.

## Start the console

Use Python 3.10 or newer from the repository root:

    pip install -r requirements-demo.txt
    streamlit run app.py

The app opens with three sample cases. You can paste a message into the inbox or import up to 100 rows from a CSV with a message, text, tweet, content, or full_text column. The review queue supports approve or reject, and the activity tab shows a downloadable log.

## Demo boundaries

- Replies remain local drafts until a reviewer approves the exact proposed action.
- Refunds require approval; deletion and unknown actions are blocked.
- Approvals are short-lived and single-use in the safety gate.
- The category and priority hints use simple keywords, and the support agent is deterministic.
- Cases, approvals, mock actions, and activity are kept in the current Streamlit session only.
- The demo operator is fixed for demonstration; it is not authentication.
- Nothing is sent to X/Twitter, a paid LLM, Kafka, or a payment provider. No API credentials are needed.

## Safety demo from the command line

    python -m safety_gate.demo
    python -m unittest safety_gate.test_gate safety_gate.test_workflow -v

See safety_gate/README.md for the safety-gate design, test coverage, and production limitations.

## Original project work

The older notebooks contain experiments for airline-tweet classification, zero-shot complaint classification, a support-flow DAG, retrieval-augmented help-center answers, call transcription, and Kafka/social-streaming ideas. They are research prototypes and are not wired into this console. The Streamlit app intentionally uses a deterministic mock agent so the safety workflow is free to run and has no live side effects.

Previous credentials committed in the repository have been revoked. The demo does not use them.
