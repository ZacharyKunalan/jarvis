"""
email.py — J.A.R.V.I.S Email Module
IMAP connection, fetch, mark read, delete, filter by sender.
Supports Gmail and Outlook. Emails are never written to disk.
"""

import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv

load_dotenv()

# ─── IMAP Server Config ───────────────────────────────────────────────────────

GMAIL_IMAP   = "imap.gmail.com"
OUTLOOK_IMAP = "outlook.office365.com"
IMAP_PORT    = 993


# ─── Connection ───────────────────────────────────────────────────────────────

def connect_gmail() -> imaplib.IMAP4_SSL:
    """Connect to Gmail via IMAP using App Password from .env."""
    address  = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not address or not password:
        raise ValueError("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env")
    conn = imaplib.IMAP4_SSL(GMAIL_IMAP, IMAP_PORT)
    conn.login(address, password)
    return conn


def connect_outlook() -> imaplib.IMAP4_SSL:
    """Connect to Outlook via IMAP using App Password from .env."""
    address  = os.getenv("OUTLOOK_ADDRESS")
    password = os.getenv("OUTLOOK_APP_PASSWORD")
    if not address or not password:
        raise ValueError("OUTLOOK_ADDRESS or OUTLOOK_APP_PASSWORD not set in .env")
    conn = imaplib.IMAP4_SSL(OUTLOOK_IMAP, IMAP_PORT)
    conn.login(address, password)
    return conn


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _decode_field(raw) -> str:
    """Decode an encoded email header field to a plain string."""
    if raw is None:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body(msg: email.message.Message) -> str:
    """Extract plain-text body from an email message object."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body.strip()


# ─── Core Functions ───────────────────────────────────────────────────────────

def fetch_unread(conn: imaplib.IMAP4_SSL, limit: int = 5) -> list[dict]:
    """
    Fetch up to `limit` unread emails from INBOX.
    Returns a list of dicts: {uid, from, subject, body, date}
    Email body content is NEVER written to disk.
    """
    conn.select("INBOX")
    status, data = conn.uid("search", None, "UNSEEN")
    if status != "OK" or not data[0]:
        return []

    uids = data[0].split()[-limit:]  # most recent first (last N)
    emails = []

    for uid in reversed(uids):
        status, msg_data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        emails.append({
            "uid":     uid.decode(),
            "from":    _decode_field(msg.get("From")),
            "subject": _decode_field(msg.get("Subject")),
            "date":    _decode_field(msg.get("Date")),
            "body":    _get_body(msg),
        })

    return emails


def fetch_from_sender(conn: imaplib.IMAP4_SSL, name: str, limit: int = 5) -> list[dict]:
    """
    Fetch emails from a sender whose name/address contains `name`.
    Searches all mail (read + unread). Returns list of email dicts.
    """
    conn.select("INBOX")
    search_str = f'FROM "{name}"'
    status, data = conn.uid("search", None, search_str)
    if status != "OK" or not data[0]:
        return []

    uids = data[0].split()[-limit:]
    emails = []

    for uid in reversed(uids):
        status, msg_data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        emails.append({
            "uid":     uid.decode(),
            "from":    _decode_field(msg.get("From")),
            "subject": _decode_field(msg.get("Subject")),
            "date":    _decode_field(msg.get("Date")),
            "body":    _get_body(msg),
        })

    return emails


def fetch_read(conn: imaplib.IMAP4_SSL, limit: int = 25) -> list[dict]:
    """
    Fetch the most recent already-read emails from INBOX.
    Returns a list of dicts: {uid, from, subject, body, date}
    """
    conn.select("INBOX")
    status, data = conn.uid("search", None, "SEEN")
    if status != "OK" or not data[0]:
        return []

    uids = data[0].split()[-limit:]
    emails = []

    for uid in reversed(uids):
        status, msg_data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        emails.append({
            "uid":     uid.decode(),
            "from":    _decode_field(msg.get("From")),
            "subject": _decode_field(msg.get("Subject")),
            "date":    _decode_field(msg.get("Date")),
            "body":    _get_body(msg),
        })

    return emails


def mark_read(conn: imaplib.IMAP4_SSL, uid: str) -> bool:
    """Mark an email as read by UID. Returns True on success."""
    conn.select("INBOX")
    status, _ = conn.uid("store", uid, "+FLAGS", "\\Seen")
    return status == "OK"


def delete_email(conn: imaplib.IMAP4_SSL, uid: str) -> bool:
    """
    Move email to Trash by UID.
    Requires explicit voice confirmation BEFORE this is called — enforced in logic.py.
    Returns True on success.
    """
    conn.select("INBOX")
    # Mark for deletion
    status, _ = conn.uid("store", uid, "+FLAGS", "\\Deleted")
    if status != "OK":
        return False
    conn.expunge()
    return True


def disconnect(conn: imaplib.IMAP4_SSL) -> None:
    """Safely close and logout the IMAP connection."""
    try:
        conn.close()
        conn.logout()
    except Exception:
        pass
