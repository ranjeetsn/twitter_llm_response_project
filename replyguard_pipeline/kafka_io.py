"""Kafka serializers and topic helpers."""

from __future__ import annotations

import json
from typing import Any

from kafka import KafkaConsumer, KafkaProducer

from replyguard_pipeline.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    RESPONSE_GROUP_ID,
    RESPONSE_REQUESTS_TOPIC,
    INCOMING_TWEETS_TOPIC,
)


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        key_serializer=lambda value: value.encode("utf-8"),
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        acks="all",
        retries=3,
    )


def create_consumer(topic: str, group_id: str) -> KafkaConsumer:
    return KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        key_deserializer=lambda value: value.decode("utf-8") if value else None,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        max_poll_records=1,
    )


def send_incoming_tweet(producer: KafkaProducer, event: dict[str, Any]) -> None:
    producer.send(
        INCOMING_TWEETS_TOPIC,
        key=event["tweet_id"],
        value=event,
    ).get(timeout=15)


def send_response_request(producer: KafkaProducer, event: dict[str, Any]) -> None:
    producer.send(
        RESPONSE_REQUESTS_TOPIC,
        key=event["tweet_id"],
        value=event,
    ).get(timeout=15)
