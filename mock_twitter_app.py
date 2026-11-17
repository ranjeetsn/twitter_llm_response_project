"""A tiny Twitter-like posting surface that writes only to local Kafka."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import streamlit as st

from replyguard_pipeline.kafka_io import create_producer, send_incoming_tweet
from replyguard_pipeline.store import ensure_database, list_tweets


@st.cache_resource
def _producer():
    return create_producer()


def main() -> None:
    st.set_page_config(page_title="Mock Twitter", page_icon="🐦", layout="centered")
    ensure_database()
    st.title("Mock Twitter")
    st.caption("A local posting surface for the ReplyGuard demo. Posts go to Kafka; nothing is sent to X/Twitter.")

    with st.form("compose-post", clear_on_submit=True):
        handle = st.text_input("Handle", value="@demo_user", max_chars=64)
        text = st.text_area("What’s happening?", max_chars=280, height=120)
        st.caption("Optional simulated account signals for the triage demo; no social-media API is used.")
        audience_col, activity_col = st.columns(2)
        with audience_col:
            followers = st.number_input(
                "Estimated followers",
                min_value=0,
                max_value=100_000_000,
                value=0,
                step=1_000,
                help="Synthetic input used as a rough potential-reach proxy. Leave 0 when unknown.",
            )
        with activity_col:
            engagements = st.number_input(
                "Engagements in the last hour",
                min_value=0,
                max_value=100_000_000,
                value=0,
                step=10,
                help="Synthetic input for recent attention; this is not fetched from a platform.",
            )
        submitted = st.form_submit_button("Post to local queue", type="primary", use_container_width=True)

    if submitted:
        if not text.strip():
            st.warning("Write a post first.")
        else:
            event = {
                "tweet_id": str(uuid.uuid4()),
                "text": text.strip(),
                "author_handle": handle.strip() or "@demo_user",
                "author_followers": int(followers),
                "engagements_last_hour": int(engagements),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                send_incoming_tweet(_producer(), event)
                st.success(f"Post {event['tweet_id'][:8]} sent to the local Kafka queue.")
            except Exception as exc:
                st.error(f"Could not reach local Kafka ({type(exc).__name__}). Start the broker and retry.")

    st.divider()
    st.subheader("Local timeline")

    @st.fragment(run_every="5s")
    def timeline() -> None:
        posts = list_tweets(limit=50)
        if not posts:
            st.info("No posts have reached the local database yet.")
            return
        for post in posts:
            status = post["response_status"] or post["tweet_status"]
            with st.container():
                st.markdown(f"**{post['author_handle']}** · {post['created_at']} · `{status}`")
                st.caption(
                    f"Simulated reach: {post['author_followers']:,} followers · "
                    f"recent activity: {post['engagements_last_hour']:,} engagements/hour"
                )
                st.write(post["text"])
                if post["draft_text"]:
                    st.caption("Suggested reply draft (not posted):")
                    st.write(post["draft_text"])
                st.divider()

    timeline()


if __name__ == "__main__":
    main()
