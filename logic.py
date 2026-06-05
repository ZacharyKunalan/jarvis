import json
from datetime import datetime
import asyncio
import edge_tts
import os
import wave
import subprocess
from playsound import playsound
import sounddevice as sd
import numpy as np
from groq import Groq
from dotenv import load_dotenv
import webrtcvad
import urllib.request

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load timetable
with open("timetable.json", "r") as f:
    timetable = json.load(f)

# ------------------------
# 🎤 PERSISTENT STT SERVER
# ------------------------

_stt_proc = None

def _get_stt():
    global _stt_proc
    if _stt_proc is None or _stt_proc.poll() is not None:
        print("Starting local STT server...")
        _stt_proc = subprocess.Popen(
            [r"stt_venv\Scripts\python.exe", "stt_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        # Wait for READY signal
        _stt_proc.stdout.readline()
        print("STT server ready.")
    return _stt_proc

# ------------------------
# 🔊 TEXT TO SPEECH
# ------------------------

async def async_speak(text):
    communicate = edge_tts.Communicate(text, voice="en-GB-RyanNeural")
    await communicate.save("response.mp3")

def speak(text):
    print("Jarvis:", text)
    try:
        asyncio.run(async_speak(text))
        playsound("response.mp3")
        os.remove("response.mp3")
    except Exception as e:
        print("TTS Error:", e)

# ------------------------
# 🎤 RAW AUDIO CAPTURE
# ------------------------

def _capture_audio(max_silent_chunks=30):
    sample_rate = 16000
    chunk_duration = 0.03
    chunk_size = int(sample_rate * chunk_duration)
    vad = webrtcvad.Vad(2)

    frames = []
    silent_chunks = 0
    speaking = False

    with sd.RawInputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=chunk_size, device=1) as stream:
        while True:
            chunk, _ = stream.read(chunk_size)
            is_speech = vad.is_speech(bytes(chunk), sample_rate)

            if is_speech:
                speaking = True
                silent_chunks = 0
                frames.append(bytes(chunk))
            elif speaking:
                silent_chunks += 1
                frames.append(bytes(chunk))
                if silent_chunks > max_silent_chunks:
                    break

    return b"".join(frames) if len(frames) > 3 else None

# ------------------------
# 🎤 TRANSCRIBE AUDIO
# ------------------------

def _transcribe(audio_bytes, min_words=1):
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
    if np.abs(audio_array).mean() < 20:
        return ""

    with wave.open("input.wav", "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_bytes)

    stt = _get_stt()
    stt.stdin.write("input.wav\n")
    stt.stdin.flush()
    text = stt.stdout.readline().strip()
    os.remove("input.wav")

    if not text or text.startswith("ERROR") or len(text.split()) < min_words:
        return ""

    FILLER_PHRASES = ["thank you", "thanks", "you", "bye", "goodbye", "see you", "see you later"]
    if text.lower().strip(".!, ") in FILLER_PHRASES:
        return ""

    print(f"You said: {text}")
    return text

# ------------------------
# 🎤 WAKE WORD LISTENER
# ------------------------

def listen_for_wake_word():
    import openwakeword
    from openwakeword.model import Model as WakeWordModel
    oww_model = WakeWordModel(wakeword_models=["hey_jarvis_v0.1"], inference_framework="onnx")

    chunk_size = 1280
    with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=chunk_size) as stream:
        while True:
            chunk, _ = stream.read(chunk_size)
            audio = np.frombuffer(bytes(chunk), dtype=np.int16)
            prediction = oww_model.predict(audio)
            score = prediction.get("hey_jarvis_v0.1", 0)
            if score > 0.7:
                oww_model.reset()
                return "hey jarvis"

# ------------------------
# 🎤 COMMAND LISTENER
# ------------------------

def listen():
    audio = _capture_audio(max_silent_chunks=30)
    if not audio:
        print("Jarvis: Didn't catch that...")
        return ""

    text = _transcribe(audio, min_words=1)
    if not text:
        print("Jarvis: Didn't catch that...")
    return text

# ------------------------
# 📅 TIMETABLE LOGIC
# ------------------------

def get_today_schedule():
    day = datetime.now().strftime("%A").lower()
    return timetable.get(day, [])

def get_next_event():
    day = datetime.now().strftime("%A").lower()
    now = datetime.now().strftime("%H:%M")
    events = timetable.get(day, [])
    for event in events:
        if event["time"] > now:
            return event
    return None

def is_timetable_query(text):
    text = text.lower()
    timetable_keywords = ["schedule", "timetable", "next class", "next event", "what do i have"]
    return any(phrase in text for phrase in timetable_keywords)

def is_add_timetable(text):
    text = text.lower()
    add_keywords = ["add to timetable", "add to my timetable", "add to schedule",
                    "add to my schedule", "put on my timetable", "put on my schedule",
                    "add event", "schedule a", "add a"]
    return any(phrase in text for phrase in add_keywords)

def _resolve_relative_days(text):
    from datetime import timedelta
    today    = datetime.now()
    tomorrow = today + timedelta(days=1)
    text = text.lower()
    text = text.replace("tomorrow", tomorrow.strftime("%A").lower())
    text = text.replace("today",    today.strftime("%A").lower())
    return text

def parse_timetable_entry(text):
    text = _resolve_relative_days(text)
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract timetable entries from natural language. "
                    "Return ONLY a JSON object with exactly these keys: "
                    "\"day\" (full lowercase weekday e.g. monday), "
                    "\"time\" (24hr format HH:MM e.g. 14:30), "
                    "\"event\" (short event name, title case). "
                    "If day is missing assume today. "
                    "If time is missing or ambiguous, set time to null. "
                    "Return ONLY the JSON, no explanation, no markdown."
                )
            },
            {"role": "user", "content": text}
        ]
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    print(f"LLM returned: {raw}")
    return json.loads(raw)

def add_to_timetable(text):
    try:
        entry = parse_timetable_entry(text)
        day   = entry["day"].lower()
        time  = entry["time"]
        event = entry["event"]

        if time is None:
            return f"What time would you like to add {event}?"

        with open("timetable.json", "r") as f:
            data = json.load(f)

        if day not in data:
            data[day] = []

        for existing in data[day]:
            if existing["time"] == time and existing["event"].lower() == event.lower():
                return f"{event} at {time} on {day.capitalize()} is already in your timetable."

        data[day].append({"time": time, "event": event})
        data[day].sort(key=lambda e: e["time"])

        with open("timetable.json", "w") as f:
            json.dump(data, f, indent=2)

        global timetable
        timetable = data

        return f"Done. I've added {event} at {time} on {day.capitalize()}."

    except Exception as e:
        print(f"Timetable parse error: {e}")
        return "Sorry, I couldn't understand that. Try saying: add dentist at 3pm on Thursday."

def handle_timetable(text):
    text = text.lower()

    if "next" in text:
        event = get_next_event()
        if event:
            return f"Next event: {event['event']} at {event['time']}"
        else:
            return "No more events today."

    elif "today" in text or "schedule" in text or "timetable" in text:
        events = get_today_schedule()
        if events:
            return "Today you have: " + ", ".join([f"{e['event']} at {e['time']}" for e in events])
        return "You have nothing scheduled today."

    else:
        return "I'm not sure which day you mean."

# ------------------------
# 🤖 AI (Weather)
# ------------------------

LATITUDE  = 51.2365
LONGITUDE = -0.5703

def get_weather(text):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        f"&timezone=Europe/London"
        f"&forecast_days=2"
    )
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    daily = data["daily"]

    if "tomorrow" in text.lower():
        idx = 1
        day_label = "Tomorrow"
    else:
        idx = 0
        day_label = "Today"

    max_t = daily["temperature_2m_max"][idx]
    min_t = daily["temperature_2m_min"][idx]
    rain  = daily["precipitation_sum"][idx]
    code  = daily["weathercode"][idx]

    conditions = {
        0: "clear skies", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        51: "light drizzle", 53: "drizzle", 61: "light rain", 63: "rain",
        71: "light snow", 73: "snow", 80: "showers", 81: "heavy showers",
        95: "thunderstorms"
    }
    condition = conditions.get(code, "mixed conditions")

    return (f"{day_label} in Guildford: {condition}, "
            f"high of {max_t}°C, low of {min_t}°C, "
            f"with {rain}mm of rain expected.")

def is_weather_query(text):
    keywords = ["weather", "temperature", "rain", "forecast", "sunny", "cold", "warm"]
    return any(word in text.lower() for word in keywords)

# ------------------------
# 🤖 AI (Groq LLM)
# ------------------------

def ask_ai(text):
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Jarvis, a personal AI assistant. "
                    "Give short, direct answers in 1-2 sentences. "
                    "Never roleplay or go off topic. "
                    "If you don't know something like real-time weather, say so briefly."
                )
            },
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content