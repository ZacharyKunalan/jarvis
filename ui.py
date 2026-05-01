import tkinter as tk
import math
import json
import os
import random
from datetime import datetime

# ── Colour palette ────────────────────────────────────────────────────────────
BG           = "#070b14"
PANEL        = "#0b1220"
PANEL_LT     = "#101a2e"
BORDER       = "#1e3a5f"
BORDER_LT    = "#2a5080"
ACCENT       = "#00d4ff"
ACCENT_DIM   = "#00506a"
ACCENT_GLOW  = "#80eeff"
ACCENT2      = "#0088cc"
AMBER        = "#ffb700"
AMBER_DIM    = "#4d3800"
AMBER_GLOW   = "#ffd060"
RED          = "#ff3b5c"
WHITE        = "#e8f6ff"
WHITE_DIM    = "#a0c8e0"
GREY         = "#1e3a55"
GREY_LT      = "#4a7a9a"
GREY_MD      = "#2e5070"
SUCCESS      = "#00ffb0"
SUCCESS_DIM  = "#005040"

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_TITLE      = ("Courier New", 13, "bold")
F_MAIN       = ("Courier New", 11, "bold")
F_MED        = ("Courier New", 10)
F_SMALL      = ("Courier New", 9)
F_XS         = ("Courier New", 8)
F_STATUS     = ("Courier New", 18, "bold")

STATE_FILE   = "jarvis_state.txt"
W, H         = 460, 660


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
        self._particle_pool = []

        self._build_ui()
        self._animate()
        self._poll_state()
        self._watch_timetable()

    # ── BUILD UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):

        # ── Top bar ───────────────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=PANEL, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Left side — logo
        left = tk.Frame(bar, bg=PANEL)
        left.pack(side="left", padx=18, pady=8)
        tk.Label(left, text="◈", bg=PANEL, fg=ACCENT,
                 font=("Courier New", 16, "bold")).pack(side="left", padx=(0, 8))
        title_col = tk.Frame(left, bg=PANEL)
        title_col.pack(side="left")
        tk.Label(title_col, text="J.A.R.V.I.S", bg=PANEL, fg=WHITE,
                 font=F_TITLE).pack(anchor="w")
        tk.Label(title_col, text="PERSONAL INTELLIGENCE SYSTEM", bg=PANEL,
                 fg=GREY_LT, font=F_XS).pack(anchor="w")

        # Right side — indicators
        right = tk.Frame(bar, bg=PANEL)
        right.pack(side="right", padx=18, pady=8)
        tk.Label(right, text="v2.0", bg=PANEL, fg=GREY_LT, font=F_XS).pack(anchor="e")
        self.dot_canvas = tk.Canvas(right, width=12, height=12,
                                    bg=PANEL, highlightthickness=0)
        self.dot_canvas.pack(anchor="e", pady=(4, 0))
        self._status_dot = self.dot_canvas.create_oval(1, 1, 11, 11,
                                                       fill=ACCENT, outline=ACCENT_GLOW,
                                                       width=1)

        # Separator
        tk.Frame(self.root, bg=ACCENT_DIM, height=1).pack(fill="x")

        # ── System stats bar ─────────────────────────────────────────────────
        stats_bar = tk.Frame(self.root, bg=PANEL_LT, height=28)
        stats_bar.pack(fill="x")
        stats_bar.pack_propagate(False)

        self._stat_items = []
        stats = [("SYS", "ONLINE"), ("NET", "ACTIVE"), ("AI", "GROQ/v3"), ("MIC", "LIVE")]
        for label, val in stats:
            f = tk.Frame(stats_bar, bg=PANEL_LT)
            f.pack(side="left", padx=18, pady=4)
            tk.Label(f, text=label, bg=PANEL_LT, fg=GREY_LT, font=F_XS).pack(side="left")
            tk.Label(f, text=" · ", bg=PANEL_LT, fg=GREY, font=F_XS).pack(side="left")
            lbl = tk.Label(f, text=val, bg=PANEL_LT, fg=ACCENT, font=F_XS)
            lbl.pack(side="left")
            self._stat_items.append(lbl)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        # ── Orb canvas ───────────────────────────────────────────────────────
        self.canvas = tk.Canvas(self.root, width=W, height=300,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        cx, cy = W // 2, 150
        self.cx, self.cy = cx, cy

        # Background grid
        for yy in range(0, 300, 20):
            alpha = "#0a0f1c" if yy % 40 == 0 else "#080c18"
            self.canvas.create_line(0, yy, W, yy, fill=alpha, width=1)
        for xx in range(0, W, 40):
            self.canvas.create_line(xx, 0, xx, 300, fill="#080c18", width=1)

        # Corner brackets
        bsize = 18
        for bx, by, signs in [(28, 28, (1,1)), (W-28, 28, (-1,1)),
                               (28, 272, (1,-1)), (W-28, 272, (-1,-1))]:
            sx, sy = signs
            self.canvas.create_line(bx, by, bx + sx*bsize, by,
                                    fill=ACCENT_DIM, width=2)
            self.canvas.create_line(bx, by, bx, by + sy*bsize,
                                    fill=ACCENT_DIM, width=2)

        # Outer decorative rings
        self.ring_xl  = self.canvas.create_oval(cx-118, cy-118, cx+118, cy+118,
                                                outline=GREY, width=1)
        self.ring_outer = self.canvas.create_oval(cx-100, cy-100, cx+100, cy+100,
                                                  outline=BORDER_LT, width=1)
        self.ring_mid = self.canvas.create_oval(cx-78, cy-78, cx+78, cy+78,
                                                outline=ACCENT_DIM, width=1)
        self.ring_inner = self.canvas.create_oval(cx-58, cy-58, cx+58, cy+58,
                                                  outline=ACCENT, width=1, dash=(5, 3))

        # Orb body
        self.orb = self.canvas.create_oval(cx-44, cy-44, cx+44, cy+44,
                                           fill="#010a14", outline=ACCENT, width=2)

        # Orb inner glow
        self.orb_glow = self.canvas.create_oval(cx-30, cy-30, cx+30, cy+30,
                                                fill="#011520", outline=ACCENT_DIM, width=1)

        # Core dot
        self.core = self.canvas.create_oval(cx-8, cy-8, cx+8, cy+8,
                                            fill=ACCENT, outline=ACCENT_GLOW, width=1)

        # Data arc
        self.data_arc = self.canvas.create_arc(cx-52, cy-52, cx+52, cy+52,
                                               start=90, extent=270,
                                               outline=ACCENT, width=2, style="arc")

        # Secondary arc
        self.data_arc2 = self.canvas.create_arc(cx-90, cy-90, cx+90, cy+90,
                                                start=45, extent=180,
                                                outline=ACCENT2, width=1, style="arc",
                                                dash=(6, 4))

        # Tick marks
        self.tick_items = []
        for i in range(32):
            angle  = math.radians(i * (360 / 32))
            length = 10 if i % 8 == 0 else (6 if i % 4 == 0 else 3)
            r_base = 62
            x1 = cx + r_base * math.cos(angle)
            y1 = cy + r_base * math.sin(angle)
            x2 = cx + (r_base + length) * math.cos(angle)
            y2 = cy + (r_base + length) * math.sin(angle)
            col  = ACCENT if i % 8 == 0 else (GREY_LT if i % 4 == 0 else GREY)
            w    = 2 if i % 8 == 0 else 1
            item = self.canvas.create_line(x1, y1, x2, y2, fill=col, width=w)
            self.tick_items.append(item)

        # Particle pool
        for _ in range(24):
            item = self.canvas.create_oval(0, 0, 0, 0, fill=ACCENT, outline="")
            self._particle_pool.append({
                "item": item, "active": False,
                "x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0,
                "life": 0, "max_life": 1, "col": ACCENT
            })

        # ── Status section ───────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        status_outer = tk.Frame(self.root, bg=BG)
        status_outer.pack(fill="x", padx=24, pady=(14, 6))

        # Status row
        status_row = tk.Frame(status_outer, bg=BG)
        status_row.pack(fill="x")

        self.status_var = tk.StringVar(value="STANDBY")
        self.status_lbl = tk.Label(status_row, textvariable=self.status_var,
                                   bg=BG, fg=ACCENT, font=F_STATUS)
        self.status_lbl.pack(side="left")

        # Blinking cursor
        self.cursor_lbl = tk.Label(status_row, text="█", bg=BG, fg=ACCENT,
                                   font=F_STATUS)
        self.cursor_lbl.pack(side="left", padx=(4, 0))

        self.sub_var = tk.StringVar(value="Awaiting wake word  ·  say 'Hey Jarvis'")
        tk.Label(status_outer, textvariable=self.sub_var,
                 bg=BG, fg=GREY_LT, font=F_SMALL).pack(anchor="w", pady=(2, 0))

        # ── Divider ───────────────────────────────────────────────────────────
        div = tk.Frame(self.root, bg=BG)
        div.pack(fill="x", padx=24, pady=8)
        tk.Frame(div, bg=BORDER_LT, height=1).pack(fill="x")

        # ── Clock / date row ─────────────────────────────────────────────────
        info_row = tk.Frame(self.root, bg=BG)
        info_row.pack(fill="x", padx=28, pady=(0, 10))

        self.clock_var = tk.StringVar()
        tk.Label(info_row, textvariable=self.clock_var,
                 bg=BG, fg=GREY_LT, font=F_XS).pack(side="left")

        self.today_var = tk.StringVar()
        tk.Label(info_row, textvariable=self.today_var,
                 bg=BG, fg=GREY_LT, font=F_XS).pack(side="right")

        self._update_clock()

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(pady=(0, 10))

        self.tt_btn = self._make_button(btn_row, "⊞  TIMETABLE", self._toggle_timetable)
        self.tt_btn.pack(side="left", padx=6)

        # ── Timetable panel ───────────────────────────────────────────────────
        self.tt_frame = tk.Frame(self.root, bg=PANEL,
                                 highlightbackground=BORDER_LT,
                                 highlightthickness=1)
        inner = tk.Frame(self.tt_frame, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        scrollbar = tk.Scrollbar(inner, orient="vertical",
                                 bg=PANEL, troughcolor=BG,
                                 activebackground=ACCENT, width=6)
        self.tt_text = tk.Text(
            inner, bg=PANEL, fg=WHITE, font=F_SMALL,
            relief="flat", height=9, width=44,
            state="disabled", padx=14, pady=10,
            yscrollcommand=scrollbar.set, wrap="word",
            cursor="arrow", insertbackground=ACCENT
        )
        scrollbar.config(command=self.tt_text.yview)
        self.tt_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tt_text.tag_config("today_hdr", foreground=ACCENT,
                                font=("Courier New", 9, "bold"))
        self.tt_text.tag_config("other_hdr", foreground=GREY_LT,
                                font=("Courier New", 9, "bold"))
        self.tt_text.tag_config("event",   foreground=WHITE,     font=F_SMALL)
        self.tt_text.tag_config("empty",   foreground=GREY_LT,   font=F_SMALL)
        self.tt_text.tag_config("time_col", foreground=AMBER_GLOW, font=F_SMALL)

    # ── BUTTON FACTORY ────────────────────────────────────────────────────────
    def _make_button(self, parent, text, cmd):
        btn = tk.Button(
            parent, text=text,
            bg=PANEL_LT, fg=ACCENT,
            activebackground=ACCENT, activeforeground=BG,
            font=F_SMALL, relief="flat", bd=0,
            padx=18, pady=9, cursor="hand2",
            highlightbackground=BORDER_LT,
            highlightthickness=1,
            command=cmd
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_DIM, fg=ACCENT_GLOW))
        btn.bind("<Leave>", lambda e: btn.config(bg=PANEL_LT, fg=ACCENT))
        return btn

    # ── CLOCK ─────────────────────────────────────────────────────────────────
    def _update_clock(self):
        now = datetime.now()
        self.clock_var.set(now.strftime("%H:%M:%S"))
        self.today_var.set(now.strftime("%a  %d %b %Y").upper())
        self.root.after(1000, self._update_clock)

    # ── TIMETABLE ─────────────────────────────────────────────────────────────
    def _toggle_timetable(self):
        if self.timetable_open:
            self.tt_frame.pack_forget()
            self.timetable_open = False
            self.tt_btn.config(text="⊞  TIMETABLE")
            self.root.geometry(f"{W}x{H}")
        else:
            self._refresh_timetable()
            self.tt_frame.pack(padx=16, pady=(0, 14), fill="x")
            self.timetable_open = True
            self.tt_btn.config(text="⊟  CLOSE")
            self.root.geometry(f"{W}x{H + 220}")

    def _refresh_timetable(self):
        DAYS  = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        today = datetime.now().strftime("%A").lower()
        data  = load_timetable()

        self.tt_text.config(state="normal")
        self.tt_text.delete("1.0", "end")

        for day in DAYS:
            events   = data.get(day, [])
            is_today = day == today
            tag      = "today_hdr" if is_today else "other_hdr"
            marker   = "▶ " if is_today else "  "
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

    # ── PARTICLES ─────────────────────────────────────────────────────────────
    def _spawn_particle(self, col=None):
        for p in self._particle_pool:
            if not p["active"]:
                angle       = random.uniform(0, 2 * math.pi)
                speed       = random.uniform(0.6, 2.5)
                p["active"] = True
                p["x"]      = float(self.cx)
                p["y"]      = float(self.cy)
                p["vx"]     = math.cos(angle) * speed
                p["vy"]     = math.sin(angle) * speed
                p["life"]   = 0
                p["max_life"] = random.randint(30, 60)
                p["col"]    = col or ACCENT
                break

    def _update_particles(self, state):
        col = AMBER if state == "speaking" else (SUCCESS if state == "listening" else ACCENT)
        if state in ("listening", "speaking", "wake") and self.tick % 3 == 0:
            self._spawn_particle(col)

        for p in self._particle_pool:
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
            p["vy"] += 0.02  # subtle gravity
            size = max(1, 4 * (1 - ratio))
            x, y = p["x"], p["y"]
            self.canvas.coords(p["item"], x-size, y-size, x+size, y+size)
            blended = self._blend(p["col"], BG, ratio ** 0.6)
            self.canvas.itemconfig(p["item"], fill=blended)

    # ── ANIMATION ─────────────────────────────────────────────────────────────
    def _animate(self):
        self.tick += 1
        t      = self.tick
        cx, cy = self.cx, self.cy
        state  = self.state

        # Cursor blink
        self.cursor_lbl.config(fg=ACCENT if (t // 18) % 2 == 0 else BG)

        if state == "idle":
            pulse    = 0.3 + 0.15 * math.sin(t * 0.025)
            r        = 44 + 3 * math.sin(t * 0.025)
            glow     = self._blend(ACCENT_DIM, ACCENT, pulse)
            glow2    = self._blend(GREY, ACCENT_DIM, pulse)
            arc_ext  = 200 + 50 * math.sin(t * 0.018)
            arc_ext2 = 120 + 40 * math.sin(t * 0.012)
            core_r   = 6 + 2 * math.sin(t * 0.025)
            dot_col  = ACCENT_DIM
            rot_spd  = 0.2
            rot_spd2 = -0.12

        elif state == "wake":
            pulse    = 0.7 + 0.3 * abs(math.sin(t * 0.08))
            r        = 44 + 8 * abs(math.sin(t * 0.08))
            glow     = self._blend(ACCENT, ACCENT_GLOW, pulse)
            glow2    = self._blend(ACCENT_DIM, ACCENT, pulse)
            arc_ext  = 320
            arc_ext2 = 200
            core_r   = 8 + 4 * abs(math.sin(t * 0.08))
            dot_col  = ACCENT_GLOW
            rot_spd  = 1.2
            rot_spd2 = -0.6

        elif state == "listening":
            pulse    = 0.5 + 0.5 * abs(math.sin(t * 0.09))
            r        = 44 + 10 * abs(math.sin(t * 0.09))
            glow     = self._blend(ACCENT, SUCCESS, pulse)
            glow2    = self._blend(ACCENT_DIM, SUCCESS_DIM, pulse)
            arc_ext  = 300 + 60 * abs(math.sin(t * 0.06))
            arc_ext2 = 180 + 80 * abs(math.sin(t * 0.04))
            core_r   = 8 + 5 * abs(math.sin(t * 0.09))
            dot_col  = SUCCESS
            rot_spd  = 1.8
            rot_spd2 = -0.9

        elif state == "speaking":
            pulse    = abs(math.sin(t * 0.15))
            r        = 44 + 12 * pulse
            glow     = self._blend(ACCENT, AMBER, pulse)
            glow2    = self._blend(ACCENT2, AMBER_DIM, pulse)
            arc_ext  = 360 * pulse
            arc_ext2 = 240 * abs(math.sin(t * 0.07))
            core_r   = 9 + 6 * pulse
            dot_col  = AMBER_GLOW
            rot_spd  = 3.0
            rot_spd2 = -1.5

        else:
            r, glow, glow2, arc_ext, arc_ext2 = 44, ACCENT, ACCENT_DIM, 200, 120
            core_r, dot_col, rot_spd, rot_spd2 = 6, ACCENT, 0.2, -0.12

        # Orb
        self.canvas.coords(self.orb, cx-r, cy-r, cx+r, cy+r)
        self.canvas.itemconfig(self.orb, outline=glow)
        self.canvas.coords(self.orb_glow, cx-(r*0.65), cy-(r*0.65),
                           cx+(r*0.65), cy+(r*0.65))
        self.canvas.itemconfig(self.orb_glow, outline=glow2)

        # Rings
        self.canvas.itemconfig(self.ring_inner, outline=glow, dash=(5, 3))
        self.canvas.itemconfig(self.ring_mid,   outline=glow2)
        self.canvas.itemconfig(self.ring_outer, outline=BORDER_LT)

        # Core
        self.canvas.coords(self.core, cx-core_r, cy-core_r, cx+core_r, cy+core_r)
        self.canvas.itemconfig(self.core, fill=dot_col, outline=self._blend(dot_col, BG, 0.4))

        # Arcs
        arc_start = (t * rot_spd * 2) % 360
        self.canvas.itemconfig(self.data_arc, start=arc_start, extent=arc_ext,
                               outline=glow)
        arc_start2 = (t * rot_spd2 * 2 + 180) % 360
        self.canvas.itemconfig(self.data_arc2, start=arc_start2, extent=arc_ext2,
                               outline=glow2)

        # Ticks
        offset = math.radians(t * rot_spd)
        for i, item in enumerate(self.tick_items):
            angle  = offset + math.radians(i * (360 / 32))
            length = 10 if i % 8 == 0 else (6 if i % 4 == 0 else 3)
            r_base = 62
            x1 = cx + r_base * math.cos(angle)
            y1 = cy + r_base * math.sin(angle)
            x2 = cx + (r_base + length) * math.cos(angle)
            y2 = cy + (r_base + length) * math.sin(angle)
            col = glow if i % 8 == 0 else (GREY_LT if i % 4 == 0 else GREY)
            self.canvas.coords(item, x1, y1, x2, y2)
            self.canvas.itemconfig(item, fill=col)

        # Particles
        self._update_particles(state)

        # Status dot
        dot_map = {"idle": GREY_LT, "wake": ACCENT_GLOW,
                   "listening": SUCCESS, "speaking": AMBER_GLOW}
        self.dot_canvas.itemconfig(self._status_dot,
                                   fill=dot_map.get(state, GREY_LT),
                                   outline=dot_map.get(state, GREY_LT))

        self.root.after(25, self._animate)

    # ── COLOUR BLEND ──────────────────────────────────────────────────────────
    def _blend(self, hex1, hex2, t):
        t  = max(0.0, min(1.0, t))
        r1, g1, b1 = int(hex1[1:3],16), int(hex1[3:5],16), int(hex1[5:7],16)
        r2, g2, b2 = int(hex2[1:3],16), int(hex2[3:5],16), int(hex2[5:7],16)
        return (f"#{int(r1+(r2-r1)*t):02x}"
                f"{int(g1+(g2-g1)*t):02x}"
                f"{int(b1+(b2-b1)*t):02x}")

    # ── STATE POLLING ─────────────────────────────────────────────────────────
    def _poll_state(self):
        new_state = read_state()
        if new_state != self.state:
            self.state = new_state
            labels = {
                "idle":      ("STANDBY",   "Awaiting wake word  ·  say 'Hey Jarvis'"),
                "wake":      ("ALERT",     "Wake word detected  ·  initialising..."),
                "listening": ("LISTENING", "Speak your command..."),
                "speaking":  ("SPEAKING",  "Processing  ·  please wait..."),
            }
            title, sub = labels.get(new_state, ("STANDBY", ""))
            self.status_var.set(title)
            self.sub_var.set(sub)

            col_map = {
                "idle":      ACCENT,
                "wake":      ACCENT_GLOW,
                "listening": SUCCESS,
                "speaking":  AMBER_GLOW,
            }
            self.status_lbl.config(fg=col_map.get(new_state, ACCENT))
            self.cursor_lbl.config(fg=col_map.get(new_state, ACCENT))

        self.root.after(200, self._poll_state)


# ── LAUNCH ────────────────────────────────────────────────────────────────────
_root_ref = None

def launch():
    global _root_ref
    root      = tk.Tk()
    app       = JarvisUI(root)
    _root_ref = root
    root.mainloop()

def shutdown():
    global _root_ref
    if _root_ref:
        _root_ref.after(0, _root_ref.destroy)

if __name__ == "__main__":
    launch()