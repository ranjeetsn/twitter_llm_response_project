"""Consume response jobs and save drafts for human review."""

from __future__ import annotations

import time

from replyguard_pipeline.config import RESPONSE_GROUP_ID, RESPONSE_REQUESTS_TOPIC
from replyguard_pipeline.kafka_io import create_consumer
from replyguard_pipeline.responder import build_responder
from replyguard_pipeline.store import (
    ensure_database,
    mark_response_failed,
    response_is_complete,
    save_response,
)


def main() -> None:
    ensure_database()
    print(
        f"Response worker listening on {RESPONSE_REQUESTS_TOPIC}; "
        "provider settings are checked for each message"
    )
    while True:
        try:
            consumer = create_consumer(RESPONSE_REQUESTS_TOPIC, RESPONSE_GROUP_ID)
            break
        except Exception as exc:
            print(f"Kafka is not ready ({type(exc).__name__}); retrying in 3 seconds.")
            time.sleep(3)

    try:
        for record in consumer:
            event = record.value
            tweet_id = str(event.get("tweet_id", ""))
            text = str(event.get("text", "")).strip()
            if not tweet_id or not text:
                print("Skipping malformed response request.")
                consumer.commit()
                continue
            if response_is_complete(tweet_id):
                consumer.commit()
                continue

            responder = None
            try:
                responder = build_responder()
                generated = responder.generate(text)
                save_response(tweet_id, generated.text, generated.model_name)
                print(f"Draft saved for {tweet_id} using {generated.model_name}.")
            except Exception as exc:
                mark_response_failed(tweet_id, f"{type(exc).__name__}: response generation failed")
                print(f"Draft generation failed for {tweet_id} ({type(exc).__name__}).")
            finally:
                if responder is not None:
                    close = getattr(responder, "close", None)
                    if close is not None:
                        try:
                            close()
                        except Exception as exc:
                            print(f"Response client cleanup failed ({type(exc).__name__}).")
            consumer.commit()
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
