# J.A.R.V.I.S — Personal AI Assistant

A voice-activated personal AI assistant with a Tkinter UI, wake word detection, timetable management, email reading, and LLM-powered responses via Groq.

## Features
- 🎤 Voice activation via wake word ("Hey Jarvis")
- 🤖 LLM responses powered by Groq (Llama 3)
- 🔊 Text-to-speech via Edge TTS (British voice)
- 📅 Timetable management — add & query events by voice
- 📧 Email reader — fetch, summarise, and manage Gmail by voice
- 🖥️ Animated Tkinter UI with state-aware orb

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/jarvis.git
cd jarvis
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** `webrtcvad` requires a C compiler on some systems.
> On Windows, install [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) first.
> On Linux: `sudo apt install python3-dev`

### 4. Add your API keys and credentials
Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```
Get a free Groq key at [console.groq.com](https://console.groq.com)

For Gmail, generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and enable IMAP in Gmail settings.

### 5. Install Ollama (required for email summarisation)
Download and install from [ollama.com/download](https://ollama.com/download), then pull the model:
```bash
ollama pull llama3.1:8b
```
Ollama runs as a background application — start it before running J.A.R.V.I.S. Email bodies are summarised entirely on-device and never sent to any external API.

### 6. Create a timetable file
```bash
echo "{}" > timetable.json
```

### 7. Run
```bash
python main.py
```

## Usage
- Say **"Hey Jarvis"** to activate
- Ask anything, or say things like:
  - *"What's on my schedule today?"*
  - *"Add dentist at 3pm on Thursday"*
  - *"What's the capital of France?"*
  - *"Any new emails?"*
  - *"Delete all LinkedIn"*
  - *"Tell me more"*
- Say **"Goodbye"** or **"Exit"** to shut down

## Dependencies
See `requirements.txt`. Key packages:
| Package | Purpose |
|---|---|
| `groq` | LLM + Whisper transcription |
| `edge-tts` | Text-to-speech |
| `sounddevice` | Microphone capture |
| `webrtcvad` | Voice activity detection |
| `python-dotenv` | API key loading |

> `tkinter` and `imaplib` are built into Python — no install needed.

> **Ollama** is a standalone application, not a pip package. Install it separately from [ollama.com/download](https://ollama.com/download). It is required for email summarisation but not for any other features.