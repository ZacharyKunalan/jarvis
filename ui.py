import tkinter as tk
from tkinter import font
import math
import json
import os
import threading
from datetime import datetime

BG         = "#080c14"
NAVY       = "#0d1526"
CYAN       = "#00d4ff"
CYAN_DIM   = "#004d5c"
WHITE      = "#e8f4f8"
GREY       = "#3a5068"
FONT_MAIN  = ("Courier New", 11)
FONT_TITLE = ("Courier New", 13, "bold")
FONT_SMALL = ("Courier New", 9)

STATE_FILE = "jarvis_state.txt"

def load_timetable():
    try:
        with open("timetable.json") as f:
            return json.load(f)
    except:
        return {}

def get_today_events():
    day = datetime.now().strftime("%A").lower()
    return load_timetable().get(day, [])

def read_state():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip()
    except:
        return "idle"

class JarvisUI:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S")
        self.root.configure(bg=BG)
        self.root.geometry("360x520")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.state = "idle"
        self.tick  = 0
        self.timetable_open = False
        self._last_mtime = None

        self._build_ui()
        self._animate()
        self._poll_state()
        self._watch_timetable()

    def _build_ui(self):
        bar = tk.Frame(self.root, bg=NAVY, height=36)
        bar.pack(fill="x")
        tk.Label(bar, text="◈  J.A.R.V.I.S", bg=NAVY, fg=CYAN,
                 font=FONT_TITLE).pack(side="left", padx=14, pady=6)
        tk.Label(bar, text="v1.0", bg=NAVY, fg=GREY,
                 font=FONT_SMALL).pack(side="right", padx=14, pady=6)

        self.canvas = tk.Canvas(self.root, width=360, height=260,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        cx, cy = 180, 130
        self.ring3 = self.canvas.create_oval(cx-90, cy-90, cx+90, cy+90,
                                             outline=CYAN_DIM, width=1)
        self.ring2 = self.canvas.create_oval(cx-68, cy-68, cx+68, cy+68,
                                             outline=CYAN_DIM, width=1)
        self.ring1 = self.canvas.create_oval(cx-48, cy-48, cx+48, cy+48,
                                             outline=CYAN, width=1)
        self.orb   = self.canvas.create_oval(cx-36, cy-36, cx+36, cy+36,
                                             fill="#001824", outline=CYAN, width=2)
        self.dot   = self.canvas.create_oval(cx-8, cy-8, cx+8, cy+8,
                                             fill=CYAN, outline="")

        self.tick_items = []
        for i in range(12):
            angle = math.radians(i * 30)
            x1 = cx + 52 * math.cos(angle)
            y1 = cy + 52 * math.sin(angle)
            x2 = cx + 58 * math.cos(angle)
            y2 = cy + 58 * math.sin(angle)
            item = self.canvas.create_line(x1, y1, x2, y2, fill=GREY, width=1)
            self.tick_items.append(item)

        self.cx, self.cy = cx, cy

        self.status_var = tk.StringVar(value="STANDBY")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=BG, fg=CYAN, font=("Courier New", 12, "bold")).pack(pady=(0, 4))

        self.sub_var = tk.StringVar(value="Waiting for wake word...")
        tk.Label(self.root, textvariable=self.sub_var,
                 bg=BG, fg=GREY, font=FONT_SMALL).pack()

        tk.Frame(self.root, bg=CYAN_DIM, height=1).pack(fill="x", padx=24, pady=12)

        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=4)

        self.timetable_btn = tk.Button(
            btn_frame, text="[ TIMETABLE ]",
            bg=NAVY, fg=CYAN, activebackground=CYAN, activeforeground=BG,
            font=FONT_MAIN, relief="flat", bd=0, padx=16, pady=6,
            cursor="hand2", command=self._toggle_timetable
        )
        self.timetable_btn.pack(side="left", padx=8)

        # Timetable panel — scrollable, all 7 days
        self.timetable_frame = tk.Frame(self.root, bg=NAVY)
        scroll_container = tk.Frame(self.timetable_frame, bg=NAVY)
        scroll_container.pack(fill="both", expand=True, padx=8, pady=8)
        scrollbar = tk.Scrollbar(scroll_container, orient="vertical",
                                 bg=NAVY, troughcolor=BG, width=8)
        self.timetable_text = tk.Text(
            scroll_container,
            bg=NAVY, fg=WHITE, font=FONT_SMALL,
            relief="flat", height=10, width=36,
            state="disabled", padx=10, pady=8,
            yscrollcommand=scrollbar.set, wrap="word"
        )
        scrollbar.config(command=self.timetable_text.yview)
        self.timetable_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.timetable_text.tag_config("today_header", foreground=CYAN,
                                       font=("Courier New", 9, "bold"))
        self.timetable_text.tag_config("other_header", foreground=GREY,
                                       font=("Courier New", 9, "bold"))
        self.timetable_text.tag_config("event_line", foreground=WHITE)
        self.timetable_text.tag_config("empty_line", foreground=GREY)

    # ── Timetable panel ──────────────────────
    def _toggle_timetable(self):
        if self.timetable_open:
            self.timetable_frame.pack_forget()
            self.timetable_open = False
            self.timetable_btn.config(text="[ TIMETABLE ]")
            self.root.geometry("360x520")
        else:
            self._refresh_timetable()
            self.timetable_frame.pack(padx=16, pady=4, fill="x")
            self.timetable_open = True
            self.timetable_btn.config(text="[ CLOSE ]")
            self.root.geometry("360x700")

    def _refresh_timetable(self):
        DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        today = datetime.now().strftime("%A").lower()
        data  = load_timetable()
        self.timetable_text.config(state="normal")
        self.timetable_text.delete("1.0", "end")
        for day in DAYS:
            events = data.get(day, [])
            tag    = "today_header" if day == today else "other_header"
            marker = "\u25b6 " if day == today else "  "
            self.timetable_text.insert("end", f"{marker}\u2500\u2500 {day.upper()} \u2500\u2500\n", tag)
            if events:
                for e in events:
                    self.timetable_text.insert("end",
                        f"    {e['time']}  \u2192  {e['event']}\n", "event_line")
            else:
                self.timetable_text.insert("end", "    No events\n", "empty_line")
            self.timetable_text.insert("end", "\n")
        self.timetable_text.config(state="disabled")
        try:
            self.timetable_text.yview_moveto(DAYS.index(today) / 7)
        except:
            pass


    # ── File watcher — auto-refresh panel ────
    def _watch_timetable(self):
        try:
            mtime = os.path.getmtime("timetable.json")
            if self._last_mtime is None:
                self._last_mtime = mtime
            elif mtime != self._last_mtime:
                self._last_mtime = mtime
                if self.timetable_open:
                    self._refresh_timetable()   # live update
        except:
            pass
        self.root.after(1000, self._watch_timetable)

    # ── Animation ────────────────────────────
    def _animate(self):
        self.tick += 1
        t = self.tick
        cx, cy = self.cx, self.cy
        state = self.state

        if state == "idle":
            scale = 1 + 0.08 * math.sin(t * 0.04)
            r = 36 * scale
            glow_col = self._blend(CYAN_DIM, CYAN, 0.3 + 0.15 * math.sin(t * 0.04))
            self.canvas.itemconfig(self.ring1, outline=glow_col)
            self.canvas.itemconfig(self.ring2, outline=CYAN_DIM)
            self.canvas.itemconfig(self.ring3, outline=CYAN_DIM)
            dot_scale = 0.7 + 0.15 * math.sin(t * 0.04)

        elif state == "listening":
            scale = 1 + 0.15 * math.sin(t * 0.12)
            r = 36 * scale
            pulse = 0.5 + 0.5 * abs(math.sin(t * 0.12))
            glow_col = self._blend(CYAN_DIM, CYAN, pulse)
            self.canvas.itemconfig(self.ring1, outline=CYAN)
            self.canvas.itemconfig(self.ring2, outline=glow_col)
            self.canvas.itemconfig(self.ring3, outline=self._blend(CYAN_DIM, CYAN, pulse * 0.5))
            dot_scale = 0.8 + 0.3 * abs(math.sin(t * 0.12))

        elif state == "speaking":
            scale = 1 + 0.2 * abs(math.sin(t * 0.2))
            r = 36 * scale
            self.canvas.itemconfig(self.ring1, outline=CYAN)
            self.canvas.itemconfig(self.ring2, outline=CYAN)
            self.canvas.itemconfig(self.ring3, outline=self._blend(CYAN_DIM, CYAN, 0.7))
            dot_scale = 1.0 + 0.5 * abs(math.sin(t * 0.2))

        else:
            r, dot_scale = 36, 1.0

        self.canvas.coords(self.orb, cx-r, cy-r, cx+r, cy+r)
        dr = 8 * dot_scale
        self.canvas.coords(self.dot, cx-dr, cy-dr, cx+dr, cy+dr)

        rot_speed = {"idle": 0.3, "listening": 1.2, "speaking": 2.0}.get(state, 0.3)
        offset = math.radians(t * rot_speed)
        for i, item in enumerate(self.tick_items):
            angle = offset + math.radians(i * 30)
            x1 = cx + 52 * math.cos(angle)
            y1 = cy + 52 * math.sin(angle)
            x2 = cx + 60 * math.cos(angle)
            y2 = cy + 60 * math.sin(angle)
            self.canvas.coords(item, x1, y1, x2, y2)

        self.root.after(30, self._animate)

    def _blend(self, hex1, hex2, t):
        t = max(0, min(1, t))
        r1,g1,b1 = int(hex1[1:3],16),int(hex1[3:5],16),int(hex1[5:7],16)
        r2,g2,b2 = int(hex2[1:3],16),int(hex2[3:5],16),int(hex2[5:7],16)
        return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

    # ── State polling ─────────────────────────
    def _poll_state(self):
        new_state = read_state()
        if new_state != self.state:
            self.state = new_state
            labels = {
                "idle":      ("STANDBY",   "Waiting for wake word..."),
                "listening": ("LISTENING", "Speak your command..."),
                "speaking":  ("SPEAKING",  "Processing response..."),
                "wake":      ("ALERT",     "Wake word detected!"),
            }
            title, sub = labels.get(new_state, ("STANDBY", ""))
            self.status_var.set(title)
            self.sub_var.set(sub)
        self.root.after(200, self._poll_state)


def launch():
    global _root_ref
    root = tk.Tk()
    app  = JarvisUI(root)
    _root_ref = root
    root.mainloop()

if __name__ == "__main__":
    launch()

_root_ref = None

def shutdown():
    """Called from voice thread to destroy the window."""
    global _root_ref
    if _root_ref:
        _root_ref.after(0, _root_ref.destroy)