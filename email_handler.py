"""
email_handler.py — J.A.R.V.I.S Email Intent Handler
"""

import re
from collections import defaultdict
from email_module import (
    connect_gmail,
    fetch_unread,
    fetch_from_sender,
    fetch_read,
    mark_read,
    delete_email,
    disconnect,
)
from email_summariser import summarise_email, expand_email, check_ollama_available

# ─── Session State ────────────────────────────────────────────────────────────

_state = {
    "active":               False,
    "queue":                [],
    "current":              None,
    "pending_delete":       False,
    "pending_delete_all":   False,   # waiting to confirm bulk delete
    "delete_all_target":    None,    # sender label for bulk delete
    "connection":           None,
    "clusters":             {},
    "cluster_order":        [],
    "in_cluster":           False,
    "showing_read":         False,   # are we browsing read emails?
    "pending_read_offer":   False,   # offered to show read emails, awaiting yes/no
}


def _reset_state():
    if _state["connection"]:
        disconnect(_state["connection"])
    _state.update({
        "active":               False,
        "queue":                [],
        "current":              None,
        "pending_delete":       False,
        "pending_delete_all":   False,
        "delete_all_target":    None,
        "connection":           None,
        "clusters":             {},
        "cluster_order":        [],
        "in_cluster":           False,
        "showing_read":         False,
        "pending_read_offer":   False,
    })


def is_email_active() -> bool:
    return _state["active"] or _state["pending_read_offer"]


# ─── Intent Detection ─────────────────────────────────────────────────────────

EMAIL_KEYWORDS = [
    r"\bemail[s]?\b",
    r"\binbox\b",
    r"\bmessage[s]?\b",
    r"\bunread\b",
    r"\bmail\b",
    r"\bheard from\b",
    r"\bgot anything\b",
    r"\bany new\b",
]

FROM_PATTERN = re.compile(
    r"(?:email[s]?|mail|message[s]?|heard)\s+(?:from|by)\s+(.+)", re.IGNORECASE
)

DELETE_ALL_PATTERN = re.compile(
    r"(?:delete|clear|remove)\s+all\s+(.+)", re.IGNORECASE
)


def is_email_query(text: str) -> bool:
    t = text.lower()
    return any(re.search(kw, t) for kw in EMAIL_KEYWORDS)


def _extract_sender_name(text: str) -> str | None:
    match = FROM_PATTERN.search(text)
    return match.group(1).strip() if match else None


def _extract_delete_all_target(text: str) -> str | None:
    match = DELETE_ALL_PATTERN.search(text)
    return match.group(1).strip() if match else None


def _sender_label(email_dict: dict) -> str:
    raw = email_dict.get("from", "Unknown")
    match = re.match(r'^"?([^"<]+)"?\s*<', raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _cluster_emails(emails: list[dict]) -> dict:
    clusters = defaultdict(list)
    for e in emails:
        clusters[_sender_label(e)].append(e)
    return dict(clusters)


def _build_cluster_intro(clusters: dict, total: int, read_mode: bool = False) -> str:
    parts = []
    for label, emails in clusters.items():
        count = len(emails)
        parts.append(f"{count} from {label}" if count > 1 else f"1 from {label}")
    if len(parts) > 1:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    else:
        joined = parts[0]
    kind = "recent" if read_mode else "unread"
    return (
        f"You have {total} {kind} email{'s' if total > 1 else ''}. "
        f"{joined}. "
        f"Which would you like to hear, say 'all' to go through them in order, "
        f"or say 'delete all' followed by a sender name to clear them."
    )


# ─── Response Builder ─────────────────────────────────────────────────────────

def _speak_summary(email_dict: dict) -> str:
    """One sentence + options."""
    summary = summarise_email(email_dict)
    return (
        f"{summary} "
        "Say 'keep it', 'delete it', 'tell me more', 'read the full one', or 'stop'."
    )


def _advance_queue() -> str:
    if not _state["queue"]:
        if _state["in_cluster"] and _state["clusters"]:
            _state["in_cluster"] = False
            _state["current"]    = None
            _state["queue"]      = []
            return (
                "That's all from that sender. "
                + _build_cluster_intro(
                    _state["clusters"],
                    sum(len(v) for v in _state["clusters"].values()),
                    _state["showing_read"],
                )
            )
        _reset_state()
        return "That's all your emails. Is there anything else?"

    _state["current"] = _state["queue"].pop(0)
    return "Next email. " + _speak_summary(_state["current"])


# ─── Main Handler ─────────────────────────────────────────────────────────────

def handle_email(text: str, speak_fn=None) -> str:
    text_lower = text.lower()

    # ── Offer to show read emails (no unread found) ───────────────────────────
    if _state["pending_read_offer"]:
        _state["pending_read_offer"] = False
        if any(w in text_lower for w in ["yes", "yeah", "sure", "go ahead", "okay"]):
            return _start_read_email_session()
        else:
            return "Okay, no problem."

    # ── Stop / exit ───────────────────────────────────────────────────────────
    if _state["active"] and any(w in text_lower for w in ["stop", "exit emails", "that's enough", "never mind", "no more"]):
        _reset_state()
        return "Okay, closing your inbox."

    # ── Confirm bulk delete ───────────────────────────────────────────────────
    if _state["pending_delete_all"]:
        if any(w in text_lower for w in ["yes", "confirm", "go ahead"]):
            label  = _state["delete_all_target"]
            conn   = _state["connection"]
            emails = _state["clusters"].get(label, [])
            for e in emails:
                delete_email(conn, e["uid"])
            del _state["clusters"][label]
            _state["pending_delete_all"] = False
            _state["delete_all_target"]  = None
            _state["current"]            = None
            _state["queue"]              = []
            remaining = sum(len(v) for v in _state["clusters"].values())
            if not remaining:
                _reset_state()
                return f"Deleted all emails from {label}. Your inbox is clear."
            return (
                f"Deleted all emails from {label}. "
                + _build_cluster_intro(_state["clusters"], remaining, _state["showing_read"])
            )
        else:
            _state["pending_delete_all"] = False
            _state["delete_all_target"]  = None
            return "Okay, keeping them. " + _build_cluster_intro(
                _state["clusters"],
                sum(len(v) for v in _state["clusters"].values()),
                _state["showing_read"],
            )

    # ── Confirm single delete ─────────────────────────────────────────────────
    if _state["pending_delete"]:
        if any(w in text_lower for w in ["yes", "confirm", "go ahead", "delete it"]):
            email = _state["current"]
            conn  = _state["connection"]
            if email and conn:
                delete_email(conn, email["uid"])
                # Remove from cluster too
                label = _sender_label(email)
                if label in _state["clusters"]:
                    _state["clusters"][label] = [
                        e for e in _state["clusters"][label] if e["uid"] != email["uid"]
                    ]
                    if not _state["clusters"][label]:
                        del _state["clusters"][label]
            _state["pending_delete"] = False
            _state["current"]        = None
            return _advance_queue()
        else:
            _state["pending_delete"] = False
            return "Okay, keeping it. " + _advance_queue()

    # ── Delete all [sender] ───────────────────────────────────────────────────
    if _state["active"]:
        delete_target = _extract_delete_all_target(text)
        if delete_target:
            # Find best matching cluster label
            matched_label = None
            for label in _state["clusters"]:
                if delete_target.lower() in label.lower() or label.lower() in delete_target.lower():
                    matched_label = label
                    break
            if matched_label:
                count = len(_state["clusters"][matched_label])
                _state["pending_delete_all"] = True
                _state["delete_all_target"]  = matched_label
                _state["current"]            = None
                return f"Are you sure you want to delete all {count} email{'s' if count > 1 else ''} from {matched_label}? Say yes to confirm."
            else:
                return f"I couldn't find any emails from {delete_target} in your inbox."

    # ── In-session commands ───────────────────────────────────────────────────
    if _state["active"] and _state["current"]:
        email = _state["current"]
        conn  = _state["connection"]

        if any(w in text_lower for w in ["keep it", "keep", "next", "move on"]):
            mark_read(conn, email["uid"])
            _state["current"] = None
            return _advance_queue()

        if any(w in text_lower for w in ["delete it", "delete", "remove", "bin it"]):
            _state["pending_delete"] = True
            subject = email.get("subject", "this email")
            return f"Are you sure you want to delete '{subject}'? Say yes to confirm."

        if any(w in text_lower for w in ["tell me more", "expand", "more detail", "elaborate"]):
            expanded = expand_email(email)
            return expanded + " Say 'keep it', 'delete it', or 'read the full one'."

        if any(w in text_lower for w in ["read the full", "full email", "read it", "read more"]):
            body = email.get("body", "The email body is empty.")
            if len(body) > 600:
                body = body[:600] + "… I've cut it there to keep it brief."
            return body

    # ── Cluster drill-down ────────────────────────────────────────────────────
    if _state["active"] and _state["clusters"] and not _state["current"]:
        if "all" in text_lower:
            all_emails = [e for emails in _state["clusters"].values() for e in emails]
            _state["queue"]      = all_emails[1:]
            _state["current"]    = all_emails[0]
            _state["in_cluster"] = False
            return "Starting from the top. " + _speak_summary(_state["current"])

        # Strip noise words before matching
        NOISE = {"from", "the", "a", "an", "all", "email", "emails", "delete",
                 "clear", "read", "show", "me", "my", "and", "or", "to", "of",
                 "please", "just", "can", "you", "play", "we", "no", "but",
                 "two", "one", "three", "four", "five", "slate", "by"}
        search_words = [w for w in text_lower.split() if w not in NOISE and len(w) > 2]

        matched_label = None
        best_score = 0
        for label in _state["clusters"]:
            label_words = set(label.lower().split()) - NOISE
            score = sum(1 for w in search_words if w in label_words or
                        any(w in lw or lw in w for lw in label_words))
            if score > best_score:
                best_score = score
                matched_label = label

        if best_score > 0 and matched_label:
            emails = _state["clusters"][matched_label]
            _state["queue"]      = emails[1:]
            _state["current"]    = emails[0]
            _state["in_cluster"] = True
            count = len(emails)
            return (
                f"{count} email{'s' if count > 1 else ''} from {matched_label}. "
                + _speak_summary(_state["current"])
            )

        # Nothing matched — if text looks off-topic, exit session and return None
        if not any(re.search(kw, text_lower) for kw in EMAIL_KEYWORDS) and not any(
            w in text_lower for w in ["keep", "delete", "stop", "all", "yes", "no", "next"]
        ):
            _reset_state()
            return None

        return (
            "I didn't catch that sender. "
            + _build_cluster_intro(
                _state["clusters"],
                sum(len(v) for v in _state["clusters"].values()),
                _state["showing_read"],
            )
        )

    # ── New email session ─────────────────────────────────────────────────────
    if not check_ollama_available():
        return "My local language model isn't running. Please start Ollama and try again."

    try:
        conn = connect_gmail()
    except ValueError as e:
        return f"I couldn't connect to Gmail: {e}"
    except Exception as e:
        return f"There was an IMAP connection error: {e}"

    _state["connection"]   = conn
    _state["active"]       = True
    _state["showing_read"] = False

    sender_name = _extract_sender_name(text)
    if sender_name:
        emails = fetch_from_sender(conn, sender_name, limit=10)
        if not emails:
            _reset_state()
            return f"I didn't find any emails from {sender_name}."
        _state["queue"]      = emails[1:]
        _state["current"]    = emails[0]
        _state["in_cluster"] = True
        count = len(emails)
        return (
            f"I found {count} email{'s' if count > 1 else ''} from {sender_name}. "
            + _speak_summary(emails[0])
        )

    # Fetch unread
    emails = fetch_unread(conn, limit=25)
    if not emails:
        # No unread — offer read emails instead
        _state["pending_read_offer"] = True
        return "You have no unread emails. Would you like me to check your recent emails instead?"

    clusters = _cluster_emails(emails)
    _state["clusters"]      = clusters
    _state["cluster_order"] = list(clusters.keys())
    return _build_cluster_intro(clusters, len(emails))


def _start_read_email_session() -> str:
    """Fetch recent read emails and present cluster overview."""
    conn = _state.get("connection")
    if not conn:
        try:
            conn = connect_gmail()
            _state["connection"] = conn
            _state["active"]     = True
        except Exception as e:
            return f"There was an IMAP connection error: {e}"

    _state["active"]       = True
    _state["showing_read"] = True

    emails = fetch_read(conn, limit=25)
    if not emails:
        _reset_state()
        return "I couldn't find any recent emails either."

    clusters = _cluster_emails(emails)
    _state["clusters"]      = clusters
    _state["cluster_order"] = list(clusters.keys())
    return _build_cluster_intro(clusters, len(emails), read_mode=True)
