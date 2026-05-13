"""
email_summariser.py — J.A.R.V.I.S Email Summariser
Uses local Ollama (llama3.1:8b) so email content never leaves the PC.
"""

import json
import urllib.request
import urllib.error

OLLAMA_URL   = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"

SHORT_PROMPT = (
    "You are a concise email assistant for a personal AI called J.A.R.V.I.S. "
    "Summarise the email in exactly 1 spoken sentence. "
    "Mention who it's from and the single most important point. "
    "Do not use bullet points, markdown, or quotation marks. "
    "Do not start with 'Here is' or any preamble. Just speak the summary directly. "
    "Do not address the user by any name or title."
)

EXPANDED_PROMPT = (
    "You are a concise email assistant for a personal AI called J.A.R.V.I.S. "
    "Summarise the email in 3-4 spoken sentences. "
    "Cover: who it's from, the main point, any details worth knowing, and any action needed. "
    "Do not use bullet points, markdown, or quotation marks. "
    "Do not start with 'Here is' or any preamble. Just speak the summary directly. "
    "Do not address the user by any name or title."
)


def _call_ollama(system_prompt: str, email_dict: dict) -> str:
    sender       = email_dict.get("from", "Unknown sender")
    subject      = email_dict.get("subject", "No subject")
    body         = email_dict.get("body", "")
    body_preview = body[:1500] if len(body) > 1500 else body

    user_content = (
        f"From: {sender}\n"
        f"Subject: {subject}\n\n"
        f"{body_preview}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "stream": False,
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "message" in result:
                return result["message"]["content"].strip()
            elif "choices" in result:
                return result["choices"][0]["message"]["content"].strip()
            else:
                return str(result)

    except urllib.error.URLError:
        return "I couldn't reach the local language model. Please make sure Ollama is running."
    except (KeyError, json.JSONDecodeError) as e:
        return f"I had trouble reading the summary response: {e}"


def summarise_email(email_dict: dict) -> str:
    """One sentence summary for initial read-out."""
    return _call_ollama(SHORT_PROMPT, email_dict)


def expand_email(email_dict: dict) -> str:
    """3-4 sentence expanded summary on request."""
    return _call_ollama(EXPANDED_PROMPT, email_dict)


def check_ollama_available() -> bool:
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False
