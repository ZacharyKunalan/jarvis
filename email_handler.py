"""
email_handler.py — J.A.R.V.I.S Email Intent Handler
"""

import re
from collections import defaultdict
from email_module import (
    connect_gmail,
    fetch_unread,
    fetch_from_sender,
    mark_read,
    delete_email,
    disconnect,
)
from email_summariser import summarise_email, check_ollama_available

# ─── Session State ────────────────────────────────────────────────────────────

_state = {
    "active":          False,
    "queue":           [],      # list of email dicts remaining to read
    "current":         None,    # email dict currently being discussed
    "pending_delete":  False,   # waiting for delete confirmation
    "connection":      None,    # live IMAP connection
    "clusters":        {},      # {sender_label: [email, ...]}
    "cluster_order":   [],      # ordered list of sender labels
    "in_cluster":      False,   # are we inside a cluster drill-down?
}


def _reset_state():
    if _state["connection"]:
        disconnect(_state["connection"])
    _state.update({
        "active":         False,
        "queue":          [],
        "current":        None,
        "pending_delete": False,
        "connection":     None,
        "clusters":       {},
        "cluster_order":  [],
        "in_cluster":     False,
    })


def is_email_active() -> bool:
    return _state["active"]


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


def is_email_query(text: str) -> bool:
    t = text.lower()
    return any(re.search(kw, t) for kw in EMAIL_KEYWORDS)


def _extract_sender_name(text: str) -> str | None:
    match = FROM_PATTERN.search(text)
    return match.group(1).strip() if match else None


def _sender_label(email_dict: dict) -> str:
    """Extract a clean display name from the From field."""
    raw = email_dict.get("from", "Unknown")
    match = re.match(r'^"?([^"<]+)"?\s*<', raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _cluster_emails(emails: list[dict]) -> dict:
    """Group emails by sender label. Returns {label: [emails]}."""
    clusters = defaultdict(list)
    for e in emails:
        clusters[_sender_label(e)].append(e)
    return dict(clusters)


def _build_cluster_intro(clusters: dict, total: int) -> str:
    """Build the spoken intro listing senders and counts."""
    parts = []
    for label, emails in clusters.items():
        count = len(emails)
        parts.append(f"{count} from {label}" if count > 1 else f"1 from {label}")
    if len(parts) > 1:
        joined = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    else:
        joined = parts[0]
    return (
        f"You have {total} unread email{'s' if total > 1 else ''}. "
        f"{joined}. "
        f"Which would you like to hear, or say 'all' to go through them in order?"
    )


# ─── Response Builder ─────────────────────────────────────────────────────────

def _speak_summary(email_dict: dict) -> str:
    summary = summarise_email(email_dict)
    return (
        f"{summary} "
        "Say 'keep it', 'delete it', 'read the full one', or 'stop' to finish."
    )


def _advance_queue() -> str:
    """Move to next email or end session."""
    if not _state["queue"]:
        if _state["in_cluster"] and _state["clusters"]:
            _state["in_cluster"] = False
            _state["current"] = None
            _state["queue"] = []
            return (
                "That's all from that sender. "
                + _build_cluster_intro(_state["clusters"], sum(len(v) for v in _state["clusters"].values()))
            )
        _reset_state()
        return "That's all your emails. Is there anything else?"

    _state["current"] = _state["queue"].pop(0)
    return "Next email. " + _speak_summary(_state["current"])


# ─── Main Handler ─────────────────────────────────────────────────────────────

def handle_email(text: str, speak_fn=None) -> str:
    text_lower = text.lower()

    # ── Stop / exit email session ─────────────────────────────────────────────
    if _state["active"] and any(w in text_lower for w in ["stop", "exit emails", "that's enough", "never mind", "no more"]):
        _reset_state()
        return "Okay, closing your inbox."

    # ── Confirm delete ────────────────────────────────────────────────────────
    if _state["pending_delete"]:
        if any(w in text_lower for w in ["yes", "confirm", "go ahead", "delete it"]):
            email = _state["current"]
            conn  = _state["connection"]
            if email and conn:
                delete_email(conn, email["uid"])
            _state["pending_delete"] = False
            _state["current"] = None
            return _advance_queue()
        else:
            _state["pending_delete"] = False
            return "Okay, keeping it. " + _advance_queue()

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

        if any(w in text_lower for w in ["read the full", "full email", "read it", "read more"]):
            body = email.get("body", "The email body is empty.")
            if len(body) > 600:
                body = body[:600] + "… I've cut it there to keep it brief."
            return body

    # ── Cluster drill-down — user names a sender ──────────────────────────────
    if _state["active"] and _state["clusters"] and not _state["current"]:
        if "all" in text_lower:
            all_emails = [e for emails in _state["clusters"].values() for e in emails]
            _state["queue"]      = all_emails[1:]
            _state["current"]    = all_emails[0]
            _state["in_cluster"] = False
            return "Starting from the top. " + _speak_summary(_state["current"])

        for label, emails in _state["clusters"].items():
            if label.lower() in text_lower or any(w in label.lower() for w in text_lower.split()):
                _state["queue"]      = emails[1:]
                _state["current"]    = emails[0]
                _state["in_cluster"] = True
                count = len(emails)
                return (
                    f"{count} email{'s' if count > 1 else ''} from {label}. "
                    + _speak_summary(_state["current"])
                )

        return (
            "I didn't catch that sender. "
            + _build_cluster_intro(_state["clusters"], sum(len(v) for v in _state["clusters"].values()))
        )

    # ── New email session ─────────────────────────────────────────────────────
    if not check_ollama_available():
        return (
            "My local language model isn't running. "
            "Please start Ollama and try again."
        )

    try:
        conn = connect_gmail()
    except ValueError as e:
        return f"I couldn't connect to Gmail: {e}"
    except Exception as e:
        return f"There was an IMAP connection error: {e}"

    _state["connection"] = conn
    _state["active"]     = True

    sender_name = _extract_sender_name(text)
    if sender_name:
        emails = fetch_from_sender(conn, sender_name, limit=5)
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

    emails = fetch_unread(conn, limit=25)
    if not emails:
        _reset_state()
        return "You have no unread emails at the moment."

    clusters = _cluster_emails(emails)
    _state["clusters"]      = clusters
    _state["cluster_order"] = list(clusters.keys())

    return _build_cluster_intro(clusters, len(emails))