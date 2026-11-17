"""Transparent, rule-based queue triage for the local social-care demo.

This is a prioritization aid, not an authorization or sentiment model. Inputs such
as audience size and recent engagement are synthetic in the mock UI.
"""

from __future__ import annotations

from typing import Any


_CRITICAL_SIGNALS = (
    "injured",
    "injury",
    "unsafe",
    "fire",
    "emergency",
    "data breach",
    "breach",
    "hacked",
    "account takeover",
    "stolen",
    "fraud",
    "identity theft",
    "exposed",
    "leaked",
)
_HIGH_SIGNALS = (
    "charged twice",
    "double charged",
    "unauthorized charge",
    "lost money",
    "payment missing",
    "account locked",
    "can't access",
    "cannot access",
    "service outage",
    "outage",
    "stranded",
)
_MODERATE_SIGNALS = (
    "refund",
    "late",
    "delay",
    "broken",
    "damaged",
    "not working",
    "cancel",
    "problem",
    "issue",
)
_IMMEDIATE_SIGNALS = (
    "right now",
    "immediately",
    "urgent",
    "emergency",
    "still happening",
    "ongoing",
)
_TIMEBOUND_SIGNALS = (
    "today",
    "within an hour",
    "in an hour",
    "deadline",
    "before my flight",
    "before tomorrow",
    "as soon as possible",
)


def _count(value: Any) -> int:
    try:
        return max(0, min(int(value or 0), 100_000_000))
    except (TypeError, ValueError, OverflowError):
        return 0


def _matches(text: str, phrases: tuple[str, ...]) -> list[str]:
    normalized = f" {text.casefold()} "
    return [phrase for phrase in phrases if f" {phrase} " in normalized]


def _reach_bucket(followers: int) -> tuple[int, str]:
    if followers <= 0:
        return 0, "Unknown"
    if followers < 10_000:
        return 15, "Small (<10K)"
    if followers < 100_000:
        return 40, "Growing (10K–99K)"
    if followers < 1_000_000:
        return 70, "Large (100K–999K)"
    return 100, "Very large (1M+)"


def _velocity_bucket(engagements: int) -> tuple[int, str]:
    if engagements <= 0:
        return 0, "No recent activity entered"
    if engagements < 10:
        return 20, "Low (<10/hour)"
    if engagements < 100:
        return 45, "Moderate (10–99/hour)"
    if engagements < 1_000:
        return 75, "High (100–999/hour)"
    return 100, "Very high (1K+/hour)"


def recommend_triage(
    text: str,
    *,
    author_followers: Any = 0,
    engagements_last_hour: Any = 0,
) -> dict[str, Any]:
    """Return an explainable recommendation for human review order.

    Severity and explicit urgency dominate. Reach and engagement can raise the
    order for otherwise similar posts, but cannot make a severe report routine.
    The result never approves, rejects, or publishes a reply.
    """
    normalized = str(text or "").casefold()
    critical = _matches(normalized, _CRITICAL_SIGNALS)
    high = _matches(normalized, _HIGH_SIGNALS)
    moderate = _matches(normalized, _MODERATE_SIGNALS)
    immediate = _matches(normalized, _IMMEDIATE_SIGNALS)
    timebound = _matches(normalized, _TIMEBOUND_SIGNALS)

    if critical:
        severity_score, severity_label = 100, "Potentially severe"
    elif high:
        severity_score, severity_label = 75, "High"
    elif moderate:
        severity_score, severity_label = 45, "Moderate"
    else:
        severity_score, severity_label = 25, "No clear harm cue detected"

    if immediate:
        urgency_score, urgency_label = 100, "Immediate wording"
    elif timebound:
        urgency_score, urgency_label = 70, "Time-bound wording"
    else:
        urgency_score, urgency_label = 0, "No explicit deadline detected"

    followers = _count(author_followers)
    engagements = _count(engagements_last_hour)
    reach_score, reach_label = _reach_bucket(followers)
    velocity_score, velocity_label = _velocity_bucket(engagements)

    # Weighted, bounded features. A severe-signal floor prevents low reach from
    # burying possible safety, privacy, security, or fraud reports.
    score = round(
        severity_score * 0.40
        + urgency_score * 0.25
        + reach_score * 0.25
        + velocity_score * 0.10
    )
    if critical:
        score = max(score, 80)

    if score >= 78:
        priority = "Urgent"
        next_step = "Escalate to a human lead now; verify facts and follow incident policy."
    elif score >= 58 or severity_score >= 75:
        priority = "High"
        next_step = "Review soon; check account, payment, or service context before replying."
    elif score >= 35:
        priority = "Elevated"
        next_step = "Review after urgent items; audience size or activity raises visibility."
    else:
        priority = "Routine"
        next_step = "Use the standard queue and decide whether a reply is useful."

    signals: list[str] = []
    if critical:
        signals.append("Potentially severe wording: " + ", ".join(critical))
    elif high:
        signals.append("Elevated harm wording: " + ", ".join(high))
    elif moderate:
        signals.append("Service issue wording: " + ", ".join(moderate))
    if immediate:
        signals.append("Immediate wording: " + ", ".join(immediate))
    elif timebound:
        signals.append("Time-bound wording: " + ", ".join(timebound))
    signals.append(f"Audience proxy: {reach_label} ({followers:,} followers entered).")
    signals.append(f"Recent activity proxy: {velocity_label} ({engagements:,} engagements entered in the last hour).")
    if not critical and not high and not moderate:
        signals.append("No configured service-harm phrase matched; check context because this rule set can miss issues.")

    return {
        "score": score,
        "priority": priority,
        "severity": severity_label,
        "urgency": urgency_label,
        "reach": reach_label,
        "velocity": velocity_label,
        "signals": signals,
        "next_step": next_step,
        "components": {
            "severity": severity_score,
            "urgency": urgency_score,
            "reach": reach_score,
            "velocity": velocity_score,
        },
    }
