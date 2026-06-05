"""
record_training.py — J.A.R.V.I.S Whisper Fine-Tuning Recorder
--------------------------------------------------------------
Records your voice for each sentence in the script.
Saves labelled .wav files + a transcript.json for Colab fine-tuning.
Supports multiple takes — run as many sessions as you like.

Usage:
    python record_training.py

Controls:
    Enter        — start recording
    Enter again  — stop recording and save
    s            — skip sentence
    q            — quit and save progress
"""

import os
import json
import numpy as np
import sounddevice as sd
import wave

# ─── Config ───────────────────────────────────────────────────────────────────

SAMPLE_RATE  = 16000
CHANNELS     = 1
OUTPUT_DIR   = "training_data"
TRANSCRIPT_F = os.path.join(OUTPUT_DIR, "transcript.json")

# ─── Sentences ────────────────────────────────────────────────────────────────

SENTENCES = [
    # ── HIGH PRIORITY — these are what Whisper struggles with most ──
    # Short commands — repeated with variations
    "Exit",
    "Exit Jarvis",
    "Exit please",
    "Quit",
    "Quit Jarvis",
    "Stop",
    "Stop Jarvis",
    "Stop please",
    "Terminate",
    "Shutdown",
    "Close",
    "Goodbye",
    "Goodbye Jarvis",
    "Bye",
    "Bye Jarvis",
    "Never mind",
    "Never mind Jarvis",
    "No more",
    "That's enough",
    "Cancel",

    # Wake word variations
    "Hey Jarvis",
    "Hey Jarvis are you there",
    "Hey Jarvis wake up",
    "Jarvis",
    "Yes",
    "Yes Jarvis",
    "Yes please",
    "No",
    "No Jarvis",
    "No thank you",

    # Single word answers
    "Keep",
    "Delete",
    "Skip",
    "Next",
    "Back",
    "All",
    "More",
    "Less",
    "Done",
    "Confirm",

    # Email commands
    "Any new emails today",
    "Do I have any emails",
    "Check my inbox",
    "Any unread emails",
    "Emails from LinkedIn",
    "Emails from David Fano",
    "Emails from Premier League",
    "Emails from Instagram",
    "Emails from Use AI",
    "Emails from Google",
    "Emails from Xbox",
    "Delete all LinkedIn",
    "Delete all Instagram",
    "Delete all Xbox",
    "Delete all Use AI",
    "Delete all David Fano",
    "Keep it",
    "Delete it",
    "Tell me more",
    "Read the full one",
    "Yes confirm delete",
    "No keep it",
    "Show me recent emails",
    "Check my recent emails",

    # Timetable commands
    "What do I have today",
    "What's on my schedule today",
    "What do I have tomorrow",
    "What do I have on Monday",
    "What do I have on Tuesday",
    "What do I have on Wednesday",
    "What do I have on Thursday",
    "What do I have on Friday",
    "What do I have on Saturday",
    "What do I have on Sunday",
    "Add dentist at three pm on Thursday",
    "Add gym at nine am on Monday",
    "Add football at six pm on Saturday",
    "Add lecture at ten am on Wednesday",
    "Add revision at two pm on Friday",
    "What's next on my schedule",
    "When is my next event",

    # Weather commands
    "What's the weather today",
    "What's the weather like today",
    "What's the weather tomorrow",
    "Will it rain today",
    "Will it rain tomorrow",
    "How cold is it today",
    "What temperature is it today",
    "Do I need an umbrella today",

    # General AI queries
    "What's the capital of France",
    "Who is the Prime Minister",
    "What time is it",
    "Tell me a fun fact",
    "What is artificial intelligence",
    "How does machine learning work",
    "What is the Premier League",
    "Who won the Champions League",
    "What is the weather in London",
    "How far is London from Guildford",
    "What is the University of Surrey known for",

    # Numbers and times
    "One two three four five six seven eight nine ten",
    "Eleven twelve thirteen fourteen fifteen",
    "Twenty thirty forty fifty",
    "One pm two pm three pm four pm five pm",
    "Nine am ten am eleven am twelve pm",
    "Half past three quarter to four",
    "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
    "January February March April May June",
    "July August September October November December",

    # Names and contacts
    "David Fano",
    "Josh from Use AI",
    "Daniel from Use AI",
    "Zachary Kunalan",
    "Premier League",
    "LinkedIn",
    "Instagram",
    "Google",
    "Xbox",
    "GitHub",
    "Microsoft",
    "Anthropic",
    "University of Surrey",

    # Natural conversational phrases
    "What can you do",
    "How are you Jarvis",
    "Thank you Jarvis",
    "That's correct",
    "That's wrong",
    "Try again",
    "Can you repeat that",
    "I didn't understand",
    "Move on",
    "Next one",
    "Go back",
    "Show me all of them",
    "Skip that one",
    "Yes that's right",
    "No that's not right",

    # Longer natural sentences
    "Hey Jarvis any new emails today",
    "Hey Jarvis what do I have on Thursday",
    "Hey Jarvis what's the weather like tomorrow",
    "Hey Jarvis delete all emails from LinkedIn",
    "Hey Jarvis add gym session at eight am on Monday",
    "Hey Jarvis tell me more about that email",
    "Hey Jarvis read the full email",
    "Hey Jarvis what's on my schedule this week",
    "Hey Jarvis do I have anything from the Premier League",
    "Hey Jarvis check my recent emails please",
    "I want to delete all the Instagram emails",
    "Show me emails from David Fano",
    "What did Use AI send me",
    "Is there anything from Google in my inbox",
    "Add a meeting at two pm on Friday afternoon",
    "What time is my next lecture",
    "Remind me about the football match on Saturday",
    "What is the weather forecast for this weekend",
    "Tell me about the latest Premier League results",
    "What are the key skills hiring managers look for",
]


# ─── Recording Logic ──────────────────────────────────────────────────────────

def record_until_enter():
    frames = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype='int16', callback=callback):
        input()

    if not frames:
        return None
    return np.concatenate(frames, axis=0)


def save_wav(audio: np.ndarray, filepath: str):
    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def load_transcript() -> dict:
    if os.path.exists(TRANSCRIPT_F):
        with open(TRANSCRIPT_F, 'r') as f:
            return json.load(f)
    return {}


def save_transcript(transcript: dict):
    with open(TRANSCRIPT_F, 'w') as f:
        json.dump(transcript, f, indent=2)


def count_takes(transcript: dict, sentence: str) -> int:
    return sum(1 for k in transcript if k.startswith(sentence))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    transcript = load_transcript()

    total       = len(SENTENCES)
    total_takes = len(transcript)
    session_num = max((count_takes(transcript, s) for s in SENTENCES), default=0) + 1

    print("\n" + "="*60)
    print("  J.A.R.V.I.S — Whisper Training Recorder")
    print("="*60)
    print(f"  Session:     {session_num}")
    print(f"  Sentences:   {total}")
    print(f"  Total takes: {total_takes}")
    print("-"*60)
    print("  Controls:")
    print("    Enter  → start recording")
    print("    Enter  → stop recording")
    print("    s      → skip sentence")
    print("    q      → quit and save")
    print("="*60 + "\n")

    input("Press Enter to begin...\n")

    skipped  = 0
    recorded = 0

    for i, sentence in enumerate(SENTENCES):
        take = count_takes(transcript, sentence) + 1
        print(f"[{i+1}/{total}] Take {take}  —  {sentence}")
        print("  Press Enter to record, 's' to skip, 'q' to quit")

        cmd = input("  > ").strip().lower()

        if cmd == 'q':
            print("\nSaving and quitting...")
            break

        if cmd == 's':
            print("  Skipped.\n")
            skipped += 1
            continue

        print("  🔴 Recording... (press Enter to stop)")
        audio = record_until_enter()

        if audio is None or len(audio) < SAMPLE_RATE * 0.3:
            print("  Too short, skipping.\n")
            skipped += 1
            continue

        safe_name = sentence.lower().replace(" ", "_").replace("'", "")[:50]
        filename  = f"{i+1:04d}_{safe_name}_t{take}.wav"
        filepath  = os.path.join(OUTPUT_DIR, filename)
        save_wav(audio, filepath)

        duration = len(audio) / SAMPLE_RATE
        transcript[f"{sentence} (take {take})"] = filename
        save_transcript(transcript)

        print(f"  ✅ Saved — {filename} ({duration:.1f}s)\n")
        recorded += 1

    print(f"\nSession {session_num} complete!")
    print(f"  Recorded: {recorded}  |  Skipped: {skipped}")
    print(f"  Total takes in dataset: {len(load_transcript())}")
    print(f"  Files saved to: {OUTPUT_DIR}/\n")


if __name__ == "__main__":
    main()