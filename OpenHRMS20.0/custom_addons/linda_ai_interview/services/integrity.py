"""Integrity signal heuristics and the AI-assistance risk roll-up (FRD §9)."""

SIGNAL_WEIGHTS = {
    "canary": "high",
    "explanation_gap": "high",
    "typing_replay": "medium",
    "reference_ai_match": "medium",
    "peer_match": "medium",
    "written_spoken_gap": "medium",
    "focus_paste": "medium",
    "ai_style": "low",
    "voice_pattern": "low",
}


def risk_level(signal_types):
    """Combine triggered signal types into Low / Medium / High.

    Any high-weight signal or two distinct medium signals -> High; one medium -> Medium.
    Low-weight signals are notes only and never raise the rating.
    """
    weights = [SIGNAL_WEIGHTS.get(t, "low") for t in set(signal_types)]
    highs, mediums = weights.count("high"), weights.count("medium")
    if highs or mediums >= 2:
        return "high"
    if mediums == 1:
        return "medium"
    return "low"


def analyse_keystrokes(events, final_text):
    """Inspect a keystroke log for copy-from-another-screen patterns.

    ``events``: list of [t_ms, kind, n] where kind is 'i' (insert n chars), 'd' (delete n chars),
    'p' (paste attempt), 'b' (blur), 'f' (focus). Returns (suspicious: bool, details: dict).
    """
    final_len = len(final_text or "")
    inserts = [e for e in events if len(e) >= 3 and e[1] == "i"]
    deletes = sum(e[2] for e in events if len(e) >= 3 and e[1] == "d")
    inserted = sum(e[2] for e in inserts)
    details = {"final_chars": final_len, "inserted": inserted, "deleted": deletes, "events": len(events)}
    if final_len < 80 or len(inserts) < 10:
        return False, details

    edit_ratio = deletes / max(inserted, 1)
    details["edit_ratio"] = round(edit_ratio, 3)

    # Long idle followed by a burst producing most of the answer.
    times = [e[0] for e in inserts]
    longest_idle, burst_share = 0, 0.0
    for i in range(1, len(times)):
        gap = times[i] - times[i - 1]
        if gap > longest_idle:
            longest_idle = gap
            after = sum(e[2] for e in inserts[i:])
            burst_share = after / max(inserted, 1)
    details["longest_idle_s"] = round(longest_idle / 1000, 1)
    details["burst_share"] = round(burst_share, 2)

    # Very uniform inter-key intervals = steady retyping.
    intervals = [b - a for a, b in zip(times, times[1:]) if 0 < b - a < 2000]
    uniform = False
    if len(intervals) > 30:
        mean = sum(intervals) / len(intervals)
        var = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        cv = (var ** 0.5) / mean if mean else 0
        details["interval_cv"] = round(cv, 3)
        uniform = cv < 0.35

    idle_burst = longest_idle > 90000 and burst_share > 0.7
    few_edits = edit_ratio < 0.02 and final_len > 200
    reasons = [name for name, hit in (("idle_then_burst", idle_burst), ("steady_retyping", uniform),
                                      ("almost_no_edits", few_edits)) if hit]
    details["reasons"] = reasons
    # Two independent patterns are needed, so normal fluent typists are not flagged.
    return len(reasons) >= 2, details


def focus_signal(event_counts):
    """event_counts: dict type -> count for blur/tab-switch/fullscreen-exit/paste attempts."""
    total = sum(event_counts.values())
    return (event_counts.get("paste", 0) >= 3 or event_counts.get("fullscreen_exit", 0) >= 3
            or total >= 6), total


def voice_pattern(silence_ms, answer_text):
    """Long silence then a fluent, list-like answer."""
    words = len((answer_text or "").split())
    listy = sum(answer_text.lower().count(m) for m in ("firstly", "secondly", "thirdly", "in conclusion",
                                                        "additionally", "furthermore")) if answer_text else 0
    return silence_ms > 10000 and words > 60 and listy >= 2
