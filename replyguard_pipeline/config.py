"""Configuration for the local-only mock social pipeline."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "replyguard.sqlite3"
DB_PATH = Path(os.environ.get("REPLYGUARD_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

INCOMING_TWEETS_TOPIC = "replyguard.tweets.incoming"
RESPONSE_REQUESTS_TOPIC = "replyguard.responses.requested"
INGEST_GROUP_ID = "replyguard-ingest-v1"
RESPONSE_GROUP_ID = "replyguard-response-v1"

LLM_PROVIDER = os.environ.get("REPLYGUARD_LLM_PROVIDER", "mock").strip().lower()
OPENAI_MODEL = os.environ.get("REPLYGUARD_OPENAI_MODEL", "").strip()
