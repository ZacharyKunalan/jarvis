import threading
import time
from logic import (is_timetable_query, handle_timetable,
                   is_add_timetable, add_to_timetable,
                   ask_ai, speak, listen_for_wake_word, listen)
import ui
from ui import launch

WAKE_WORD  = "jarvis"
EXIT_WORDS = ["exit", "quit", "goodbye", "bye", "stop", "shutdown", "close", "terminate"]
STATE_FILE = "jarvis_state.txt"

def set_state(state):
    with open(STATE_FILE, "w") as f:
        f.write(state)

def is_exit(text):
    return any(word in text.lower().strip() for word in EXIT_WORDS)

def run_jarvis():
    set_state("idle")
    speak("Jarvis online. Say 'Hey Jarvis' when you need me.")
    print("Waiting for wake word: 'Hey Jarvis'...")

    while True:
        set_state("idle")
        wake_text = listen_for_wake_word()

        if not wake_text:
            continue

        if is_exit(wake_text):
            set_state("idle")
            speak("Goodbye!")
            ui.shutdown()   # close the window
            return

        if WAKE_WORD not in wake_text.lower():
            continue

        set_state("wake")
        speak("Yes?")

        while True:
            set_state("listening")
            text = listen()

            if not text:
                print("Nothing heard, going back to sleep.")
                break

            if is_exit(text):
                set_state("idle")
                speak("Goodbye!")
                ui.shutdown()   # close the window
                return

            set_state("speaking")

            if is_add_timetable(text):
                response = add_to_timetable(text)
            elif is_timetable_query(text):
                response = handle_timetable(text)
            else:
                response = ask_ai(text)

            speak(response)
            time.sleep(0.3)

if __name__ == "__main__":
    jarvis_thread = threading.Thread(target=run_jarvis, daemon=True)
    jarvis_thread.start()

    try:
        launch()
    except KeyboardInterrupt:
        print("\nJarvis shut down.")