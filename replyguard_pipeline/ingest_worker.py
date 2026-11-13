"""Consume mock posts, persist them locally, then enqueue response jobs."""

from __future__ import annotations

import time

from replyguard_pipeline.config import INGEST_GROUP_ID, INCOMING_TWEETS_TOPIC
from replyguard_pipeline.kafka_io import create_consumer, create_producer, send_response_request
from replyguard_pipeline.store import ensure_database, queue_response, record_tweet


def main() -> None:
    ensure_database()
    print(f"Ingest worker listening on {INCOMING_TWEETS_TOPIC}")
    while True:
        try:
            consumer = create_consumer(INCOMING_TWEETS_TOPIC, INGEST_GROUP_ID)
            producer = create_producer()
            break
        except Exception as exc:
            print(f"Kafka is not ready ({type(exc).__name__}); retrying in 3 seconds.")
            time.sleep(3)

    try:
        for record in consumer:
            event = record.value
            tweet_id = str(event.get("tweet_id", ""))
            text = str(event.get("text", "")).strip()
            if not tweet_id or not text or len(text) > 280:
                print("Skipping malformed or over-limit post.")
                consumer.commit()
                continue

            try:
                record_tweet(event)
                if queue_response(tweet_id):
                    send_response_request(
                        producer,
                        {
                            "tweet_id": tweet_id,
                            "text": text,
                            "created_at": event.get("created_at", ""),
                        },
                    )
                consumer.commit()
                print(f"Stored {tweet_id} locally and queued its response job.")
            except Exception as exc:
                print(f"Could not finish {tweet_id} ({type(exc).__name__}); leaving it uncommitted.")
                raise
    finally:
        consumer.close()
        producer.flush(timeout=5)
        producer.close(timeout=5)


if __name__ == "__main__":
    main()
