"""
stt_server.py — Persistent Whisper STT server
Runs in stt_venv, stays loaded between calls.
Communicates via stdin/stdout pipes.
Run with: stt_venv\Scripts\python.exe stt_server.py
"""

import sys
import os
import wave
import numpy as np

# Suppress loading messages
sys.stderr = open(os.devnull, 'w')

from local_stt import transcribe

# Signal ready to parent process
sys.stdout.write("READY\n")
sys.stdout.flush()

while True:
    try:
        # Wait for a wav file path from parent
        line = sys.stdin.readline()
        if not line:
            break
        wav_path = line.strip()
        if not wav_path:
            continue

        if not os.path.exists(wav_path):
            sys.stdout.write("ERROR: file not found\n")
            sys.stdout.flush()
            continue

        with wave.open(wav_path, 'r') as wf:
            frames = wf.readframes(wf.getnframes())
            audio  = np.frombuffer(frames, dtype=np.int16)

        result = transcribe(audio)
        sys.stdout.write(result + "\n")
        sys.stdout.flush()

    except Exception as e:
        sys.stdout.write(f"ERROR: {e}\n")
        sys.stdout.flush()