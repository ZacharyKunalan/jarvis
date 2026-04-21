import tkinter as tk
from tkinter import font
import math
import json
import os
import threading
from datetime import datetime

# ── Colour palette ───────────────────────────────────────────────────────────
BG          = "#05080f"
PANEL       = "#090e1a"
BORDER      = "#0f1e35"
ACCENT      = "#00c8f0"
ACCENT_DIM  = "#003d52"
ACCENT_GLOW = "#00eaff"
AMBER       = "#f0a500"
AMBER_DIM   = "#3d2900"
RED         = "#ff3b5c"
WHITE       = "#d6edf5"
GREY        = "#2a4460"
GREY_LT     = "#4a6880"
SUCCESS     = "#00e5a0"

# ── Fonts ────────────────────────────────────────────────────────────────────
F_MONO_LG   = ("Courier New", 13, "bold")
F_MONO_MD   = ("Courier New", 10)
F_MONO_SM   = ("Courier New", 8)
F_MONO_XS   = ("Courier New", 7)

STATE_FILE  = "jarvis_state.txt"
W, H        = 380, 560

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_timetable():
    try:
        with open("timetable.json") as f:
            return json.load(f)
    except:
        return {}

def read_state():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip()
    except:
        return "idle"


class JarvisUI:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S  //  PERSONAL AI")
        self.root.configure(bg=BG)
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.state          = "idle"
        self.tick           = 0
        self.timetable_open = False
        self._last_mtime    = None
        self._particles     = []

        self._build_ui()
        self._animate()
        self._poll_state()
        self._watch_timetable()

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=PANEL, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="◈", bg=PANEL, fg=ACCENT,
                 font=("Courier New", 14, "bold")).pack(side="left", padx=(16, 6), pady=10)
        tk.Label(bar, text="J.A.R.V.I.S", bg=PANEL, fg=WHITE,
                 font=("Courier New", 12, "bold")).pack(side="left", pady=10)

        # Status dot (right side)
        self.dot_indicator = tk.Canvas(bar, width=10, height=10,
                                       bg=PANEL, highlightthickness=0)
        self.dot_indicator.pack(side="right", padx=(0, 16), pady=17)
        self._status_dot = self.dot_indicator.create_oval(0, 0, 9, 9,
                                                          fill=ACCENT, outline="")

        tk.Label(bar, text="v1.0", bg=PANEL, fg=GREY_LT,
                 font=F_MONO_XS).pack(side="right", padx=(0, 6), pady=10)

        # Thin accent line under bar
        tk.Frame(self.root, bg=ACCENT_DIM, height=1).pack(fill="x")

        # ── Canvas (orb) ─────────────────────────────────────────────────────
        self.canvas = tk.Canvas(self.root, width=W, height=240,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        cx, cy = W // 2, 120
        self.cx, self.cy = cx, cy

        # Decorative corner marks
        for x, y, a1, a2 in [(20, 20, 0, 90), (W-20, 20, 90, 180),
                              (20, 220, 270, 360), (W-20, 220, 180, 270)]:
            self.canvas.create_arc(x-12, y-12, x+12, y+12,
                                   start=a1, extent=90,
                                   outline=GREY, width=1, style="arc")

        # Scanline texture (subtle horizontal lines)
        for yy in range(0, 240, 6):
            self.canvas.create_line(0, yy, W, yy, fill="#0a0f1c", width=1)

        # Orbit rings
        self.ring_outer = self.canvas.create_oval(
            cx-95, cy-95, cx+95, cy+95, outline=BORDER, width=1)
        self.ring_mid   = self.canvas.create_oval(
            cx-70, cy-70, cx+70, cy+70, outline=ACCENT_DIM, width=1)
        self.ring_inner = self.canvas.create_oval(
            cx-50, cy-50, cx+50, cy+50, outline=ACCENT, width=1, dash=(4, 4))

        # Orb body
        self.orb = self.canvas.create_oval(
            cx-38, cy-38, cx+38, cy+38,
            fill="#010a12", outline=ACCENT, width=2)

        # Centre dot
        self.core = self.canvas.create_oval(
            cx-7, cy-7, cx+7, cy+7, fill=ACCENT, outline="")

        # Tick marks around orbit
        self.tick_items = []
        for i in range(24):
            angle = math.radians(i * 15)
            length = 8 if i % 6 == 0 else 4
            x1 = cx + 53 * math.cos(angle)
            y1 = cy + 53 * math.sin(angle)
            x2 = cx + (53 + length) * math.cos(angle)
            y2 = cy + (53 + length) * math.sin(angle)
            col = GREY_LT if i % 6 == 0 else GREY
            item = self.canvas.create_line(x1, y1, x2, y2, fill=col, width=1)
            self.tick_items.append(item)

        # Data arc (progress-style arc around orb)
        self.data_arc = self.canvas.create_arc(
            cx-45, cy-45, cx+45, cy+45,
            start=90, extent=270,
            outline=ACCENT, width=2, style="arc")

        # Particle pool (pre-create invisible dots)
        self._particle_items = []
        for _ in range(18):
            item = self.canvas.create_oval(0, 0, 0, 0, fill=ACCENT, outline="")
            self._particle_items.append({"item": item, "active": False,
                                         "x": 0.0, "y": 0.0,
                                         "vx": 0.0, "vy": 0.0,
                                         "life": 0, "max_life": 1})

        # ── Status area ───────────────────────────────────────────────────────
        status_frame = tk.Frame(self.root, bg=BG)
        status_frame.pack(pady=(0, 2))

        self.status_var = tk.StringVar(value="STANDBY")
        self.status_lbl = tk.Label(status_frame, textvariable=self.status_var,
                                   bg=BG, fg=ACCENT,
                                   font=("Courier New", 15, "bold"))
        self.status_lbl.pack()

        self.sub_var = tk.StringVar(value="Awaiting wake word  ·  say 'Hey Jarvis'")
        tk.Label(status_frame, textvariable=self.sub_var,
                 bg=BG, fg=GREY_LT, font=F_MONO_SM).pack(pady=(2, 0))

        # ── Divider ───────────────────────────────────────────────────────────
        div = tk.Frame(self.root, bg=BG)
        div.pack(fill="x", padx=24, pady=10)
        tk.Frame(div, bg=ACCENT_DIM, height=1).pack(fill="x")

        # ── Info row ──────────────────────────────────────────────────────────
        info_row = tk.Frame(self.root, bg=BG)
        info_row.pack(fill="x", padx=28, pady=(0, 8))

        self.clock_var = tk.StringVar()
        tk.Label(info_row, textvariable=self.clock_var,
                 bg=BG, fg=GREY_LT, font=F_MONO_XS).pack(side="left")

        self.today_var = tk.StringVar()
        tk.Label(info_row, textvariable=self.today_var,
                 bg=BG, fg=GREY_LT, font=F_MONO_XS).pack(side="right")

        self._update_clock()

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(pady=(0, 8))

        self.tt_btn = self._make_button(btn_row, "⊞  TIMETABLE",
                                        self._toggle_timetable)
        self.tt_btn.pack(side="left", padx=6)

        # ── Timetable panel ───────────────────────────────────────────────────
        self.tt_frame = tk.Frame(self.root, bg=PANEL,
                                 highlightbackground=BORDER,
                                 highlightthickness=1)
        inner = tk.Frame(self.tt_frame, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        scrollbar = tk.Scrollbar(inner, orient="vertical",
                                 bg=PANEL, troughcolor=BG,
                                 activebackground=ACCENT, width=6)
        self.tt_text = tk.Text(
            inner, bg=PANEL, fg=WHITE, font=F_MONO_SM,
            relief="flat", height=9, width=38,
            state="disabled", padx=14, pady=10,
            yscrollcommand=scrollbar.set, wrap="word",
            cursor="arrow", insertbackground=ACCENT
        )
        scrollbar.config(command=self.tt_text.yview)
        self.tt_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tt_text.tag_config("today_hdr",
                                foreground=ACCENT,
                                font=("Courier New", 8, "bold"))
        self.tt_text.tag_config("other_hdr",
                                foreground=GREY_LT,
                                font=("Courier New", 8, "bold"))
        self.tt_text.tag_config("event",  foreground=WHITE,  font=F_MONO_SM)
        self.tt_text.tag_config("empty",  foreground=GREY,   font=F_MONO_SM)
        self.tt_text.tag_config("time_col", foreground=AMBER, font=F_MONO_SM)

    # ─────────────────────────────────────────────────────────────────────────
    # BUTTON FACTORY
    # ─────────────────────────────────────────────────────────────────────────
    def _make_button(self, parent, text, cmd):
        btn = tk.Button(
            parent, text=text,
            bg=PANEL, fg=ACCENT,
            activebackground=ACCENT, activeforeground=BG,
            font=F_MONO_SM, relief="flat", bd=0,
            padx=14, pady=7, cursor="hand2",
            highlightbackground=BORDER,
            highlightthickness=1,
            command=cmd
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_DIM, fg=ACCENT_GLOW))
        btn.bind("<Leave>", lambda e: btn.config(bg=PANEL, fg=ACCENT))
        return btn

    # ─────────────────────────────────────────────────────────────────────────
    # CLOCK
    # ─────────────────────────────────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.now()
        self.clock_var.set(now.strftime("%H:%M:%S"))
        self.today_var.set(now.strftime("%a  %d %b %Y").upper())
        self.root.after(1000, self._update_clock)

    # ─────────────────────────────────────────────────────────────────────────
    # TIMETABLE PANEL
    # ─────────────────────────────────────────────────────────────────────────
    def _toggle_timetable(self):
        if self.timetable_open:
            self.tt_frame.pack_forget()
            self.timetable_open = False
            self.tt_btn.config(text="⊞  TIMETABLE")
            self.root.geometry(f"{W}x{H}")
        else:
            self._refresh_timetable()
            self.tt_frame.pack(padx=16, pady=(0, 12), fill="x")
            self.timetable_open = True
            self.tt_btn.config(text="⊟  CLOSE")
            self.root.geometry(f"{W}x{H + 200}")

    def _refresh_timetable(self):
        DAYS  = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        today = datetime.now().strftime("%A").lower()
        data  = load_timetable()

        self.tt_text.config(state="normal")
        self.tt_text.delete("1.0", "end")

        for day in DAYS:
            events = data.get(day, [])
            is_today = day == today
            tag = "today_hdr" if is_today else "other_hdr"
            marker = "▶ " if is_today else "  "
            self.tt_text.insert("end",
                f"{marker}── {day.upper()} {'(TODAY)' if is_today else '─'*8}\n", tag)
            if events:
                for e in events:
                    self.tt_text.insert("end", f"    {e['time']}", "time_col")
                    self.tt_text.insert("end", f"  →  {e['event']}\n", "event")
            else:
                self.tt_text.insert("end", "    No events scheduled\n", "empty")
            self.tt_text.insert("end", "\n")

        self.tt_text.config(state="disabled")
        try:
            self.tt_text.yview_moveto(DAYS.index(today) / 7)
        except:
            pass

    def _watch_timetable(self):
        try:
            mtime = os.path.getmtime("timetable.json")
            if self._last_mtime is None:
                self._last_mtime = mtime
            elif mtime != self._last_mtime:
                self._last_mtime = mtime
                if self.timetable_open:
                    self._refresh_timetable()
        except:
            pass
        self.root.after(1000, self._watch_timetable)

    # ─────────────────────────────────────────────────────────────────────────
    # PARTICLES
    # ─────────────────────────────────────────────────────────────────────────
    def _spawn_particle(self):
        import random
        for p in self._particle_items:
            if not p["active"]:
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(0.8, 2.2)
                p["active"]   = True
                p["x"]        = float(self.cx)
                p["y"]        = float(self.cy)
                p["vx"]       = math.cos(angle) * speed
                p["vy"]       = math.sin(angle) * speed
                p["life"]     = 0
                p["max_life"] = random.randint(25, 50)
                break

    def _update_particles(self, state):
        if state in ("listening", "speaking") and self.tick % 4 == 0:
            self._spawn_particle()

        for p in self._particle_items:
            if not p["active"]:
                self.canvas.coords(p["item"], 0, 0, 0, 0)
                continue
            p["life"] += 1
            ratio = p["life"] / p["max_life"]
            if ratio >= 1:
                p["active"] = False
                self.canvas.coords(p["item"], 0, 0, 0, 0)
                continue
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            size = max(1, 3 * (1 - ratio))
            x, y = p["x"], p["y"]
            self.canvas.coords(p["item"], x-size, y-size, x+size, y+size)
            # Fade colour
            col = self._blend(ACCENT, BG, ratio ** 0.5)
            self.canvas.itemconfig(p["item"], fill=col)

    # ─────────────────────────────────────────────────────────────────────────
    # ANIMATION
    # ─────────────────────────────────────────────────────────────────────────
    def _animate(self):
        self.tick += 1
        t     = self.tick
        cx, cy = self.cx, self.cy
        state  = self.state

        # ── State-driven visuals ──────────────────────────────────────────────
        if state == "idle":
            pulse  = 0.3 + 0.12 * math.sin(t * 0.03)
            r      = 38 + 3  * math.sin(t * 0.03)
            glow   = self._blend(ACCENT_DIM, ACCENT, pulse)
            self.canvas.itemconfig(self.ring_inner, outline=glow, dash=(4, 4))
            self.canvas.itemconfig(self.ring_mid,   outline=ACCENT_DIM)
            self.canvas.itemconfig(self.ring_outer, outline=BORDER)
            self.canvas.itemconfig(self.orb,        outline=glow)
            core_r = 5 + 2 * math.sin(t * 0.03)
            arc_ext = 200 + 40 * math.sin(t * 0.02)
            dot_col = ACCENT_DIM
            rot_spd = 0.25

        elif state == "wake":
            pulse  = 0.7 + 0.3 * abs(math.sin(t * 0.1))
            r      = 38 + 6  * abs(math.sin(t * 0.1))
            glow   = self._blend(ACCENT, ACCENT_GLOW, pulse)
            self.canvas.itemconfig(self.ring_inner, outline=ACCENT_GLOW, dash=())
            self.canvas.itemconfig(self.ring_mid,   outline=glow)
            self.canvas.itemconfig(self.ring_outer, outline=ACCENT_DIM)
            self.canvas.itemconfig(self.orb,        outline=ACCENT_GLOW)
            core_r = 7 + 3 * abs(math.sin(t * 0.1))
            arc_ext = 300
            dot_col = ACCENT_GLOW
            rot_spd = 1.0

        elif state == "listening":
            pulse  = 0.5 + 0.5 * abs(math.sin(t * 0.1))
            r      = 38 + 8  * abs(math.sin(t * 0.1))
            glow   = self._blend(ACCENT, ACCENT_GLOW, pulse)
            self.canvas.itemconfig(self.ring_inner, outline=ACCENT_GLOW, dash=())
            self.canvas.itemconfig(self.ring_mid,   outline=glow)
            self.canvas.itemconfig(self.ring_outer, outline=self._blend(ACCENT_DIM, ACCENT, pulse * 0.4))
            self.canvas.itemconfig(self.orb,        outline=ACCENT_GLOW)
            core_r = 7 + 4 * abs(math.sin(t * 0.1))
            arc_ext = 300 + 60 * abs(math.sin(t * 0.07))
            dot_col = ACCENT_GLOW
            rot_spd = 1.5

        elif state == "speaking":
            pulse  = abs(math.sin(t * 0.18))
            r      = 38 + 10 * pulse
            glow   = self._blend(ACCENT, AMBER, pulse)
            self.canvas.itemconfig(self.ring_inner, outline=glow, dash=())
            self.canvas.itemconfig(self.ring_mid,   outline=self._blend(ACCENT, AMBER, pulse * 0.6))
            self.canvas.itemconfig(self.ring_outer, outline=ACCENT_DIM)
            self.canvas.itemconfig(self.orb,        outline=glow)
            core_r = 8 + 5 * pulse
            arc_ext = 360 * pulse
            dot_col = glow
            rot_spd = 2.5

        else:
            r, core_r, arc_ext, dot_col, rot_spd = 38, 5, 200, ACCENT, 0.25

        # Orb resize
        self.canvas.coords(self.orb, cx-r, cy-r, cx+r, cy+r)

        # Core dot
        self.canvas.coords(self.core, cx-core_r, cy-core_r, cx+core_r, cy+core_r)
        self.canvas.itemconfig(self.core, fill=dot_col)

        # Data arc
        arc_start = (t * rot_spd * 2) % 360
        self.canvas.itemconfig(self.data_arc, start=arc_start, extent=arc_ext)

        # Tick rotation
        offset = math.radians(t * rot_spd)
        for i, item in enumerate(self.tick_items):
            angle  = offset + math.radians(i * 15)
            length = 8 if i % 6 == 0 else 4
            x1 = cx + 53 * math.cos(angle)
            y1 = cy + 53 * math.sin(angle)
            x2 = cx + (53 + length) * math.cos(angle)
            y2 = cy + (53 + length) * math.sin(angle)
            self.canvas.coords(item, x1, y1, x2, y2)

        # Particles
        self._update_particles(state)

        # Status dot colour
        dot_map = {"idle": GREY_LT, "wake": ACCENT_GLOW,
                   "listening": SUCCESS, "speaking": AMBER}
        self.dot_indicator.itemconfig(
            self._status_dot, fill=dot_map.get(state, GREY_LT))

        self.root.after(28, self._animate)

    # ─────────────────────────────────────────────────────────────────────────
    # COLOUR BLEND
    # ─────────────────────────────────────────────────────────────────────────
    def _blend(self, hex1, hex2, t):
        t = max(0.0, min(1.0, t))
        r1,g1,b1 = int(hex1[1:3],16), int(hex1[3:5],16), int(hex1[5:7],16)
        r2,g2,b2 = int(hex2[1:3],16), int(hex2[3:5],16), int(hex2[5:7],16)
        return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

    # ─────────────────────────────────────────────────────────────────────────
    # STATE POLLING
    # ─────────────────────────────────────────────────────────────────────────
    def _poll_state(self):
        new_state = read_state()
        if new_state != self.state:
            self.state = new_state
            labels = {
                "idle":      ("STANDBY",   "Awaiting wake word  ·  say 'Hey Jarvis'"),
                "wake":      ("ALERT",     "Wake word detected!"),
                "listening": ("LISTENING", "Speak your command..."),
                "speaking":  ("SPEAKING",  "Processing response..."),
            }
            title, sub = labels.get(new_state, ("STANDBY", ""))
            self.status_var.set(title)
            self.sub_var.set(sub)

            # Colour the status label
            col_map = {"idle": ACCENT, "wake": ACCENT_GLOW,
                       "listening": SUCCESS, "speaking": AMBER}
            self.status_lbl.config(fg=col_map.get(new_state, ACCENT))

        self.root.after(200, self._poll_state)


# ─────────────────────────────────────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────────────────────────────────────
_root_ref = None

def launch():
    global _root_ref
    root     = tk.Tk()
    app      = JarvisUI(root)
    _root_ref = root
    root.mainloop()

def shutdown():
    global _root_ref
    if _root_ref:
        _root_ref.after(0, _root_ref.destroy)

if __name__ == "__main__":
    launch()