"""Desktop interface. Tk owns widgets, protocols, detection and disk writes.

Acquisition, protocol analysis and speech run in workers; workers never access
Tk widgets. Analysis uses completed windows and returns results to Tk.
"""
from collections import deque
from dataclasses import asdict
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
import webbrowser

import numpy as np

from .calibration import Window, calibrate, evaluate
from .config import DATA_HOME, WORDS, PHRASES, Profile
from .control import MenuController
from .detection import BlinkEngine, DETECTOR_VERSION
from .protocol import make_protocol
from .sources import DemoSource, LSLSource, discover, describe_stream
from .speech import SpeechWorker
from .storage import SessionWriter

BG = "#0b1220"
PANEL = "#142033"
CARD = "#1b2a41"
TEXT = "#eef4ff"
MUTED = "#a6b7ce"
ACCENT = "#60d9ce"
BLUE = "#64a6ff"
RED = "#ff8998"


class Application:
    def __init__(self, root, data_root=None, profile_root=None):
        self.root = root
        self.data_root = Path(data_root or DATA_HOME / "data")
        self.profile_root = Path(profile_root or DATA_HOME / "profiles")
        self.source = self.meta = self.writer = self.engine = self.profile = None
        self.last_folder = None
        self.last_data_wall = None
        self.connected_at = None
        self.validated = False
        self.streams = []
        self.scan_results = queue.Queue()
        self.scanning = False
        self.closing = False
        self.menu = MenuController()
        self.speaker = SpeechWorker()
        self.plot = deque(maxlen=4000)
        self.protocol_kind = None
        self.analysis_job = None
        self.analysis_results = queue.Queue()
        self.retry_until = None
        self.protocol_repeats = 0
        self.steps = []
        self.step_index = -1
        self.step_start = None
        self.windows = []
        self.active_window = None
        self.frozen_profile_id = None
        self.profile_path = None
        self.log_lines = 0
        self.flat_warning = False
        self._build()
        self.root.report_callback_exception = self.callback_error
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _: self.pause("Paused with Escape."))
        self.poll_timer = self.root.after(25, self.poll)
        self.refresh_buttons()

    def label(self, parent, text, size=11, color=TEXT, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size), **kwargs)

    def button(self, parent, text, command, accent=False, **kwargs):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else CARD,
                         fg=BG if accent else TEXT, activebackground=BLUE, activeforeground=BG,
                         disabledforeground="#65768e", relief="flat", bd=0,
                         font=("Segoe UI", 11, "bold"), padx=12, pady=9, cursor="hand2", **kwargs)

    def _build(self):
        self.root.title("Blink to Speak | blink_emg")
        self.root.geometry("1240x880")
        self.root.minsize(1060, 790)
        self.root.configure(bg=BG)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=TEXT, padding=(16, 10), font=("Segoe UI", 11))
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", ACCENT)])
        style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=TEXT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", TEXT)])
        style.configure("Blink.Horizontal.TProgressbar", troughcolor=CARD, background=ACCENT, borderwidth=0)

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(16, 12))
        self.label(header, "Blink to Speak", 25).pack(side="left")
        self.badge = self.label(header, "OFFLINE", 10, MUTED, padx=12, pady=6)
        self.badge.pack(side="right")
        self.label(header, "Your words. A few blinks.", 12, MUTED).pack(side="left", padx=22)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=24)
        side = tk.Frame(body, bg=PANEL, width=270, padx=16, pady=14)
        side.pack(side="left", fill="y", padx=(0, 18))
        side.pack_propagate(False)
        self.label(side, "1  CONNECT", 11, ACCENT, anchor="w").pack(fill="x", pady=(0, 6))
        self.label(side, "Connect in Chords LSL Connector,\nthen scan here.", 10, MUTED,
                   justify="left", wraplength=235).pack(fill="x", pady=(0, 8))
        discovery_row = tk.Frame(side, bg=PANEL)
        discovery_row.pack(fill="x")
        self.scan_button = self.button(discovery_row, "Scan for NPG", self.scan)
        self.scan_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.demo_button = self.button(discovery_row, "Practice", self.practice)
        self.demo_button.pack(side="left", fill="x", expand=True)
        self.stream_var = tk.StringVar()
        self.stream_picker = ttk.Combobox(side, textvariable=self.stream_var, state="readonly", width=23)
        self.stream_picker.pack(fill="x", pady=7)
        connection_row = tk.Frame(side, bg=PANEL)
        connection_row.pack(fill="x")
        self.connect_button = self.button(connection_row, "Connect", self.connect, accent=True)
        self.connect_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.disconnect_button = self.button(connection_row, "Save & disconnect", self.disconnect)
        self.disconnect_button.pack(side="left", fill="x", expand=True)
        self.connection = self.label(side, "No signals connected.", 10, MUTED, justify="left", wraplength=235, anchor="w")
        self.connection.pack(fill="x", pady=(8, 15))

        self.label(side, "2  LEARN YOUR BLINKS", 11, ACCENT, anchor="w").pack(fill="x")
        self.channel_a = tk.BooleanVar(value=True)
        self.channel_b = tk.BooleanVar(value=True)
        for text, variable in (("CH1 / A0P forehead pad", self.channel_a), ("CH2 / A1P forehead pad", self.channel_b)):
            tk.Checkbutton(side, text=text, variable=variable, bg=PANEL, fg=TEXT, selectcolor=CARD,
                           activebackground=PANEL, activeforeground=TEXT, font=("Segoe UI", 10),
                           command=self.channel_changed).pack(anchor="w")
        self.calibrate_button = self.button(side, "Start guided calibration", lambda: self.start_protocol("calibration"))
        self.calibrate_button.pack(fill="x", pady=(7, 5))
        self.quick_check_button = self.button(side, "Quick check (45 sec)", lambda: self.start_protocol("quick"))
        self.quick_check_button.pack(fill="x", pady=(0, 5))
        self.check_button = self.button(side, "Test on fresh blinks (1 min)", lambda: self.start_protocol("validation"))
        self.check_button.pack(fill="x")
        self.cancel_button = self.button(side, "Cancel guided recording", self.cancel_protocol)
        self.cancel_button.pack(fill="x", pady=5)

        self.label(side, "3  USE YOUR WORDS", 11, ACCENT, anchor="w").pack(fill="x", pady=(12, 6))
        self.arm_button = self.button(side, "Start blink control", self.toggle_control, accent=True)
        self.arm_button.pack(fill="x")
        self.pause_button = self.button(side, "Pause / cancel pending", self.pause)
        self.pause_button.pack(fill="x", pady=5)
        self.audio_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(side, text="Speak words aloud", variable=self.audio_enabled, bg=PANEL, fg=TEXT,
                       selectcolor=CARD, activebackground=PANEL, activeforeground=TEXT,
                       command=self.audio_changed, font=("Segoe UI", 10)).pack(anchor="w")
        self.sidebar_hint = self.label(side, "Escape = pause\nSingle blink = no action", 10, MUTED, justify="left")
        self.sidebar_hint.pack(anchor="w", pady=7)
        for b in (self.scan_button, self.demo_button, self.connect_button, self.disconnect_button,
                  self.calibrate_button, self.quick_check_button, self.check_button, self.cancel_button, self.arm_button, self.pause_button):
            b.configure(font=("Segoe UI", 10, "bold"), padx=5, pady=5)
        self.disconnect_button.configure(text="Disconnect")

        self.tabs = ttk.Notebook(body)
        self.tabs.pack(side="left", fill="both", expand=True)
        self.communicate = tk.Frame(self.tabs, bg=PANEL, padx=20, pady=16)
        signals = tk.Frame(self.tabs, bg=PANEL, padx=18, pady=16)
        setup = tk.Frame(self.tabs, bg=PANEL, padx=20, pady=16)
        settings = tk.Frame(self.tabs, bg=PANEL, padx=20, pady=16)
        for frame, name in ((self.communicate, "Words"), (signals, "Signals & log"), (setup, "Setup guide"), (settings, "Settings & files")):
            self.tabs.add(frame, text=name)

        self.cue_title = self.label(self.communicate, "Welcome. Start with a connection.", 23, ACCENT, wraplength=740, anchor="w", justify="left")
        self.cue_title.pack(fill="x", pady=(0, 8))
        self.cue_detail = self.label(self.communicate,
            "Have your board ready? Click Scan for NPG.\nWant to explore first? Click Practice.",
            12, MUTED, justify="left", wraplength=740, anchor="w")
        self.cue_detail.pack(fill="x")
        self.progress_text = self.label(self.communicate, "", 10, MUTED, anchor="w")
        self.progress_text.pack(fill="x", pady=(8, 4))
        self.progress = ttk.Progressbar(self.communicate, style="Blink.Horizontal.TProgressbar", maximum=100)
        self.progress.pack(fill="x", pady=(0, 14))
        self.readiness = self.label(self.communicate, "Waiting for signals", 11, MUTED, anchor="w", justify="left", wraplength=740)
        self.readiness.pack(fill="x", pady=(0, 12))
        guide = tk.Frame(self.communicate, bg=CARD, padx=12, pady=10)
        guide.pack(fill="x", pady=(0, 14))
        self.label(guide, "2 blinks → next word       3 blinks → speak highlighted word", 12).pack(anchor="w")
        self.label(guide, "Blink about half a second apart. Wait for the highlight or spoken word before starting again.", 10, MUTED,
                   wraplength=690, justify="left").pack(anchor="w", pady=(3, 0))
        grid = tk.Frame(self.communicate, bg=PANEL)
        grid.pack(fill="both", expand=True)
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="word")
        for row in range(2):
            grid.rowconfigure(row, weight=1, uniform="word")
        self.tiles = []
        for i, word in enumerate(WORDS):
            tile = self.button(grid, word, lambda index=i: self.pick_word(index))
            tile.configure(font=("Segoe UI", 23, "bold"), pady=16)
            tile.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
            self.tiles.append(tile)
        self.spoken = self.label(self.communicate, "Selected: Water", 17, TEXT, anchor="w", wraplength=740)
        self.spoken.pack(fill="x", pady=(16, 6))
        manual = tk.Frame(self.communicate, bg=PANEL)
        manual.pack(fill="x")
        self.button(manual, "Speak selected (mouse)", self.manual_speak).pack(side="left")
        self.long_check_button = self.button(manual, "Longer test (5 min)", lambda: self.start_protocol("validation", extended=True))
        self.long_check_button.pack(side="left", padx=8)
        self.button(manual, "Test speaker", lambda: self.say("Blink to Speak is ready.")).pack(side="right")
        self.demo_controls = tk.Frame(self.communicate, bg=PANEL)
        self.demo_controls.pack(fill="x", pady=(12, 0))
        self.demo_inject_buttons = []
        for count in (1, 2, 3):
            b = self.button(self.demo_controls, f"Practice: {count} blink{'s' if count > 1 else ''}", lambda n=count: self.inject(n))
            b.pack(side="left", padx=(0, 6))
            self.demo_inject_buttons.append(b)

        self.label(signals, "Live forehead signals", 20).pack(anchor="w")
        self.signal_stats = self.label(signals, "No signal yet.", 11, MUTED, anchor="w", wraplength=740)
        self.signal_stats.pack(fill="x", pady=8)
        self.canvas = tk.Canvas(signals, bg=BG, highlightthickness=0, height=300)
        self.canvas.pack(fill="both", expand=True)
        self.label(signals, "Last 8 seconds • filtered native units • white lines = trigger levels\nA graph cannot confirm pad contact. Verify with guided blinks.",
                   10, MUTED, anchor="w", justify="left").pack(fill="x", pady=8)
        self.label(signals, "Activity log", 13).pack(anchor="w", pady=(7, 5))
        self.log = tk.Text(signals, height=9, bg=BG, fg=MUTED, font=("Consolas", 10), relief="flat", padx=10, pady=8, state="disabled", wrap="word")
        self.log.pack(fill="x")

        self._setup_guide(setup)
        self.label(settings, "Personal detection settings", 20).pack(anchor="w")
        self.label(settings, "Calibrate first. Adjust only if needed, then run the fresh-blink test again.",
                   11, MUTED, anchor="w", wraplength=730).pack(fill="x", pady=8)
        self.sensitivity = tk.DoubleVar(value=1.0)
        self.group_gap = tk.DoubleVar(value=0.8)
        self.label(settings, "Trigger level multiplier: lower detects weaker signals; higher rejects more signals.",
                   11, wraplength=730, justify="left").pack(anchor="w", pady=(15, 0))
        tk.Scale(settings, from_=0.65, to=1.6, resolution=0.05, orient="horizontal", variable=self.sensitivity,
                 bg=PANEL, fg=TEXT, troughcolor=CARD, highlightthickness=0, length=480).pack(anchor="w")
        self.label(settings, "Maximum time between blinks in one group (seconds).", 11).pack(anchor="w", pady=(18, 0))
        tk.Scale(settings, from_=0.5, to=1.2, resolution=0.05, orient="horizontal", variable=self.group_gap,
                 bg=PANEL, fg=TEXT, troughcolor=CARD, highlightthickness=0, length=480).pack(anchor="w")
        self.settings_button = self.button(settings, "Apply & require a new test", self.apply_settings)
        self.settings_button.pack(anchor="w", pady=12)
        self.profile_detail = self.label(settings, "No calibration saved yet.", 11, MUTED, justify="left", wraplength=730, anchor="w")
        self.profile_detail.pack(fill="x", pady=10)
        self.label(settings, "Your recordings", 20).pack(anchor="w", pady=(25, 6))
        self.recording_detail = self.label(settings, "Recordings save automatically while connected.\nNo need to make separate files for each gesture.",
                    11, MUTED, anchor="w", justify="left", wraplength=730)
        self.recording_detail.pack(fill="x")
        self.button(settings, "Open recordings folder", self.open_recordings).pack(anchor="w", pady=14)
        self.label(settings, "Each session includes raw samples.csv, timestamped events.jsonl,\nmetadata.json, and calibration / validation reports when completed.\n\nAll processing and speech happen on this laptop. No recordings are uploaded.",
                   11, MUTED, justify="left", wraplength=730).pack(anchor="w", pady=8)

        self.status = self.label(self.root, "Ready • connect NPG or explore practice mode", 10, MUTED, anchor="w")
        self.status.pack(fill="x", padx=24, pady=(10, 12))
        self.update_tiles()

    def _setup_guide(self, parent):
        self.label(parent, "Four pads. Easy forehead placement.", 20, ACCENT).pack(anchor="w")
        self.label(parent, "This app uses eye blinks. It does not read imagined words.\nThe folder is named blink_emg; the useful signal here is mainly the eye signal (EOG).",
                   11, MUTED, wraplength=730, justify="left").pack(anchor="w", pady=10)
        text = (
            "1. A0P / CH1: on bare forehead above your LEFT eyebrow.\n\n"
            "2. A1P / CH2: on bare forehead above your RIGHT eyebrow.\n\n"
            "3. REF: on the bony skin behind your LEFT ear.\n\n"
            "4. CN: on the bony skin behind your RIGHT ear.\n\n"
            "Use the CN position for the A0 and A1 common-negative switches.\n"
            "With CN enabled, leave A0N and A1N empty. Pads must not touch.\n"
            "Unused channels are recorded but are ignored for blink detection.\n\n"
            "Only one forehead pad? Use A0P near the middle of your forehead,\n"
            "keep REF and CN, and uncheck CH2 before calibration.\n\n"
            "Run the board on its battery, with USB unplugged while wearing pads.\n"
            "Keep your current raw-signal BLE firmware. No reflash is needed.\n\n"
            "Open Chords LSL Connector → Bluetooth → connect your NPG.\n"
            "Disconnect Chords Web from the board if it is using that Bluetooth link.\n"
            "Then Scan for NPG here, choose its stream, and Connect.\n\n"
            "Calibration: follow the screen for about 75 seconds.\n"
            "Fresh-blink test: follow new double / triple cues for about 2 minutes.\n"
            "Once the check passes, click Start blink control."
        )
        guide_frame = tk.Frame(parent, bg=PANEL)
        guide_frame.pack(fill="both", expand=True, pady=6)
        guide_text = tk.Text(guide_frame, wrap="word", bg=PANEL, fg=TEXT, font=("Segoe UI", 11),
                             relief="flat", borderwidth=0, highlightthickness=0, width=30, height=15,
                             padx=3, pady=3, spacing1=2, spacing3=3)
        scrollbar = ttk.Scrollbar(guide_frame, orient="vertical", command=guide_text.yview)
        guide_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        guide_text.pack(side="left", fill="both", expand=True)
        guide_text.insert("1.0", text)
        guide_text.configure(state="disabled")
        self.button(parent, "Manufacturer's placement guide", lambda: webbrowser.open("https://docs.upsidedownlabs.tech/software/applications/m2w/index.html#placing-the-electrodes")).pack(anchor="w", pady=10)

    def log_event(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S  ") + text + "\n")
        self.log_lines += 1
        if self.log_lines > 250:
            self.log.delete("1.0", "2.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def mark(self, kind, **detail):
        if self.writer:
            self.writer.event(kind, self.source.clock() if self.source else None, **detail)

    def selected_channels(self):
        return [ch for ch, enabled in enumerate((self.channel_a.get(), self.channel_b.get()))
                if enabled and (not self.meta or ch < self.meta["channels"])]

    def channel_changed(self):
        self.pause("Forehead channel choice changed.")
        self.cancel_protocol(quiet=True)
        self.validated = False
        self.profile = None
        if self.engine:
            self.engine.profile = self.engine.pulse = self.engine.grouper = None
        self.readiness.config(text="Channel choice changed. Run guided calibration again.")
        self.refresh_buttons()

    def scan(self):
        if self.scanning or self.source:
            return
        self.scanning = True
        self.status.config(text="Looking for local LSL streams…")
        self.refresh_buttons()

        def work():
            try:
                self.scan_results.put((discover(), None))
            except Exception as exc:
                self.scan_results.put(([], str(exc)))
        threading.Thread(target=work, daemon=True, name="blink-stream-discovery").start()

    def connect(self):
        index = self.stream_picker.current()
        if not 0 <= index < len(self.streams) or self.source:
            return
        self.source = LSLSource(self.streams[index])
        self.start_source()

    def practice(self):
        if self.source:
            return
        self.source = DemoSource()
        self.start_source()

    def start_source(self):
        self.connected_at = time.monotonic()
        self.last_data_wall = None
        self.plot.clear()
        self.status.config(text="Connecting…")
        self.source.start()
        self.refresh_buttons()

    def on_ready(self, metadata):
        self.meta = metadata
        self.engine = BlinkEngine(metadata["sample_rate"], metadata["channels"])
        self.writer = SessionWriter(metadata, self.data_root)
        self.last_folder = self.writer.folder
        self.profile_path = self.profile_root / ("practice.json" if metadata["simulated"] else "npg.json")
        self.profile = None
        self.validated = False
        if metadata["simulated"]:
            self.profile = Profile(0, 35, metadata["sample_rate"], metadata["source_key"], 2, 110,
                                   calibration={"simulated": True}, validation={"passed": True, "simulated": True})
            self.validated = True
        elif self.profile_path.exists():
            try:
                saved = Profile.load(self.profile_path)
                if (saved.source_key == metadata["source_key"] and saved.channel in self.selected_channels()
                        and abs(saved.sample_rate - metadata["sample_rate"]) < 0.01):
                    self.profile = saved
                    self.log_event("Loaded personal calibration. A fresh check is required after reconnecting.")
            except (ValueError, TypeError, OSError) as exc:
                self.log_event(f"Saved calibration could not be loaded: {exc}")
        if self.profile:
            self.engine.set_profile(self.profile)
        self.badge.config(text="PRACTICE • SYNTHETIC" if metadata["simulated"] else "NPG • LIVE", fg=ACCENT)
        self.connection.config(text=f"{metadata['name']}\n{metadata['channels']} channels • {metadata['sample_rate']:g} Hz\nRecording automatically.")
        self.recording_detail.config(text=f"Current recording:\n{self.writer.folder}\n\nSamples and event markers save automatically.")
        self.cue_title.config(text="Practice mode" if metadata["simulated"] else "Connected. Let's learn your blinks.")
        self.cue_detail.config(text=("These signals are computer-generated. Click Start blink control, then use the practice blink buttons.\nYou can also try the guided recordings; practice supplies those blinks automatically."
                                   if metadata["simulated"] else "Follow guided calibration first. The screen will tell you exactly when to blink.\nDo not imagine hand movements or words."))
        self.readiness.config(text="Practice ready — this does not measure real-world accuracy." if metadata["simulated"] else
                              "Saved calibration loaded. Run the fresh-blink test." if self.profile else "Next: Start guided calibration.")
        self.profile_summary()
        self.log_event("Connected to " + metadata["name"] + (" (synthetic)." if metadata["simulated"] else "."))
        self.mark("profile_loaded", profile=self.profile.to_dict() if self.profile else None)
        self.refresh_buttons()

    def disconnect(self, error=None):
        if self.source is None:
            return
        try:
            self.pause("Disconnected." if not error else error)
            self.cancel_protocol(quiet=True)
        except Exception as exc:
            # A full/unavailable disk must never prevent stopping acquisition
            # or leave communication armed just because a marker could not save.
            self.menu.pause()
            self.protocol_kind = None
            self.analysis_job = None
            self.active_window = None
            self.speaker.cancel_pending()
            if self.engine:
                self.engine.cancel()
            error = error or f"Could not save the final event marker: {exc}"
            self.log_event(f"Stopping despite a recording error: {exc}")
        source, self.source = self.source, None
        try:
            source.stop()
        except Exception as exc:
            error = error or f"Could not finish stopping the signal source: {exc}"
        if self.writer:
            try:
                self.writer.close("error" if error else "complete", error)
                self.log_event(f"Recording saved: {self.writer.folder}")
            except Exception as exc:
                error = f"Recording could not finish saving: {exc}. Existing files remain in {self.writer.folder}."
                self.log_event(error)
            self.writer = None
        self.meta = self.engine = self.profile = None
        self.validated = False
        self.last_data_wall = None
        self.badge.config(text="OFFLINE", fg=RED if error else MUTED)
        self.connection.config(text="Disconnected. Reconnect when ready.")
        self.readiness.config(text="Blink control paused. Connect and check your blinks before using it again.")
        self.cue_title.config(text="Connection needs attention" if error else "Recording saved")
        self.cue_detail.config(text=error or f"Your files are in:\n{self.last_folder}")
        self.status.config(text=error or "Disconnected • recording saved")
        self.refresh_buttons()

    def is_fresh(self):
        return (self.last_data_wall is not None and time.monotonic() - self.last_data_wall < 0.5
                and self.engine is not None and self.engine.last_timestamp is not None
                and self.source.clock() >= self.engine.warm_until)

    def start_protocol(self, kind, extended=False):
        if not self.meta or not self.is_fresh() or self.protocol_kind or self.analysis_job:
            self.status.config(text="Wait for two seconds of fresh signals, then try again.")
            return
        if not self.selected_channels():
            self.status.config(text="Check at least one forehead channel in the left panel.")
            return
        if kind in ("validation", "quick") and not self.profile:
            self.status.config(text="Run guided calibration first, then test your blinks.")
            return
        self.pause("Guided recording started.")
        self.validated = False
        self.protocol_kind = kind
        self.retry_until = None
        self.protocol_repeats = 0
        seed = int(time.time_ns() & 0xffffffff)
        self.steps = make_protocol(kind, seed, extended=extended)
        self.windows = []
        self.step_index = -1
        self.frozen_profile_id = self.profile.profile_id if self.profile else None
        self.mark("protocol_start", protocol=kind, seed=seed, extended=extended, profile=self.profile.to_dict() if self.profile else None,
                  steps=[asdict(s) for s in self.steps], candidates=self.selected_channels(), detector_version=DETECTOR_VERSION)
        self.tabs.select(self.communicate)
        self.next_step()
        self.refresh_buttons()

    def next_step(self):
        self.step_index += 1
        self.engine.cancel()
        if self.step_index >= len(self.steps):
            self.finish_protocol()
            return
        step = self.steps[self.step_index]
        # Timestamp after rendering the software cue. Physical display latency
        # is not measured; reported accuracy is coarse gesture-window accuracy.
        self.cue_title.config(text=step.title)
        self.cue_detail.config(text=step.detail)
        self.root.update_idletasks()
        self.step_start = self.source.clock()
        self.active_window = Window(step.label, self.step_start, self.step_start + step.seconds)
        self.windows.append(self.active_window)
        # Use the exact window start, not a second clock read a few microseconds
        # later, so saved cue invalidations and replay identify the same attempt.
        self.writer.event("cue", self.step_start, protocol=self.protocol_kind, index=self.step_index, **asdict(step))
        if isinstance(self.source, DemoSource):
            count = {"SINGLE": 1, "NEXT": 2, "SELECT": 3}.get(step.label)
            if count:
                self.source.inject(count, delay=0.7)
            elif step.label == "NORMAL":
                for delay in range(4, int(step.seconds) - 1, 5):
                    self.source.inject(1, delay=delay)

    def interrupt_guided_step(self, reason):
        """Retake a transport-interrupted cue; never score its partial data."""
        if not self.protocol_kind:
            return False
        if self.active_window is not None:
            interrupted = self.active_window
            self.windows.remove(interrupted)
            self.mark("cue_invalidated", protocol=self.protocol_kind,
                      cue_timestamp=interrupted.start, index=self.step_index, reason=reason)
            self.active_window = None
            self.protocol_repeats += 1
        self.retry_until = self.source.clock() + 2
        self.menu.pause()
        self.validated = False
        self.engine.cancel()
        self.speaker.cancel_pending()
        self.cue_title.config(text="Waiting for steady signals")
        self.cue_detail.config(text="Relax for a moment. The interrupted instruction will repeat automatically.\nEarlier completed steps are kept.")
        self.readiness.config(text=reason + " The interrupted attempt will not count toward your score.")
        self.progress_text.config(text="Connection pause — waiting for fresh signals before repeating this step.")
        return True

    def advance_protocol(self):
        if not self.protocol_kind:
            return
        now = self.source.clock()
        if self.retry_until is not None:
            if now >= self.retry_until and self.is_fresh():
                self.retry_until = None
                self.step_index -= 1
                self.next_step()
            return
        step = self.steps[self.step_index]
        remaining = max(0, self.step_start + step.seconds - now)
        elapsed = sum(s.seconds for s in self.steps[:self.step_index]) + step.seconds - remaining
        total = sum(s.seconds for s in self.steps)
        self.progress["value"] = 100 * elapsed / total
        self.progress_text.config(text=f"{math.ceil(remaining)}s left in this step • {math.ceil(total - elapsed)}s total remaining")
        if now >= self.active_window.end + 0.1:
            self.next_step()

    def finish_protocol(self):
        kind = self.protocol_kind
        if kind is None or self.analysis_job:
            return
        self.protocol_kind = None
        self.active_window = None
        self.engine.cancel()
        self.menu.pause()
        self.validated = False
        # Finished windows no longer receive samples. Workers never touch Tk,
        # the live engine or disk writers; acquisition continues during fitting.
        job = dict(kind=kind, session_id=self.writer.session_id,
                   profile_id=self.frozen_profile_id, channels=self.selected_channels(),
                   repeated_steps=self.protocol_repeats)
        self.analysis_job = job
        windows = tuple(self.windows)
        rate, source_key = self.meta["sample_rate"], self.meta["source_key"]
        profile = Profile(**self.profile.to_dict()) if self.profile else None
        results = self.analysis_results
        self.mark("protocol_analysis_start", protocol=kind)
        self.cue_title.config(text="Checking your recording…")
        self.cue_detail.config(text="Keep the board connected. Signals are still being recorded.")
        self.progress["value"] = 100
        self.progress_text.config(text="Recording finished. Checking the result; blink control is paused.")
        self.refresh_buttons()

        def work():
            started = time.monotonic()
            try:
                if kind == "calibration":
                    result = calibrate(windows, rate, job["channels"], source_key, job["session_id"])
                else:
                    result = evaluate(windows, profile, job["session_id"], quick=kind == "quick")
                error = None
            except Exception as exc:
                result, error = None, str(exc)
            results.put((job, result, error, time.monotonic() - started))

        threading.Thread(target=work, daemon=True, name="blink-protocol-analysis").start()

    def collect_analysis_results(self):
        while True:
            try:
                job, result, error, elapsed = self.analysis_results.get_nowait()
            except queue.Empty:
                return
            # Escape, a signal gap, disconnect or a new session revokes a job.
            if (job is not self.analysis_job or not self.writer
                    or self.writer.session_id != job["session_id"]):
                continue
            self.analysis_job = None
            self.apply_analysis_result(job, result, error, elapsed)

    def apply_analysis_result(self, job, result, error, elapsed):
        kind = job["kind"]
        try:
            if error:
                raise ValueError(error)
            if kind == "calibration":
                self.profile = result
                self.profile.calibration["repeated_steps"] = job["repeated_steps"]
                self.engine.set_profile(self.profile)
                self.profile.save(self.profile_path)
                self.writer.artifact("calibration.json", self.profile.to_dict())
                self.cue_title.config(text="Your blinks are calibrated")
                self.cue_detail.config(text=f"CH{self.profile.channel + 1} gave the clearest results.\nNext: Test on fresh blinks. This uses new double and triple blinks.")
                self.readiness.config(text=f"Calibration: {self.profile.calibration['correctly_counted']}/8 single blinks counted correctly. Fresh test required.")
                self.log_event("Personal calibration saved. Fresh-data check is next.")
                self.sensitivity.set(1)
                self.group_gap.set(self.profile.group_gap)
            else:
                if not self.profile or self.profile.profile_id != job["profile_id"]:
                    raise ValueError("Calibration changed during the test. Run a new test.")
                result["simulated"] = self.meta["simulated"]
                result["repeated_steps"] = job["repeated_steps"]
                quick = kind == "quick"
                self.validated = not quick and result["passed"]
                if not quick:
                    self.profile.validation = result
                    self.profile.save(self.profile_path)
                self.writer.artifact("quick_check.json" if quick else "validation.json", result)
                summary = (f"{result['correct_trials']}/{result['total_trials']} correct • "
                           f"{result['accidental_commands']} accidental commands in {result['normal_seconds']:.0f}s normal blinking • "
                           f"{result['extra_commands']} extra commands • {result['commands_during_waiting']} while waiting")
                self.cue_title.config(text="Quick check finished" if quick else
                                     "Practice check passed" if self.validated and self.meta["simulated"] else
                                     "Fresh-blink check passed" if self.validated else "Let's improve the detection")
                self.cue_detail.config(text=summary + ("\nPractise opening your eyes fully between blinks, about half a second apart.\nWhen comfortable, run Test on fresh blinks to enable control." if quick else
                    "\nReady: click Start blink control." if self.validated else
                    "\nCheck forehead contact and your blink spacing. Recalibrate or adjust Settings, then test again."))
                self.readiness.config(text=("Synthetic results only. " if self.meta["simulated"] else "") +
                                      ("Quick practice feedback; full test required for blink control. " if quick else
                                       "Short personal check; not a long-term accuracy guarantee. ") + summary)
                self.log_event(summary)
            self.mark("protocol_complete", protocol=kind, profile_id=self.profile.profile_id,
                      analysis_seconds=elapsed)
            self.profile_summary()
        except (ValueError, OSError) as exc:
            self.validated = False
            if kind == "calibration":
                self.profile = None
                self.engine.profile = self.engine.pulse = self.engine.grouper = None
            self.cue_title.config(text="Recording finished — needs another try")
            self.cue_detail.config(text=str(exc))
            self.readiness.config(text="Calibration / test did not pass. Your raw recording is saved.")
            self.mark("protocol_failed", protocol=kind, error=str(exc))
            self.log_event(str(exc))
        self.progress["value"] = 100
        self.progress_text.config(text="Quick check finished. Run Test on fresh blinks before starting control." if kind == "quick" else
                                  "Guided recording finished. Blink control remains paused until you start it.")
        self.refresh_buttons()

    def cancel_protocol(self, quiet=False):
        if not self.protocol_kind and not self.analysis_job:
            return
        kind = self.protocol_kind or self.analysis_job["kind"]
        self.protocol_kind = self.analysis_job = None
        self.retry_until = None
        self.active_window = None
        self.validated = False
        if self.engine:
            self.engine.cancel()
        self.mark("protocol_cancelled", protocol=kind)
        self.log_event("Guided recording cancelled; partial raw data retained.")
        if not quiet:
            self.cue_title.config(text="Guided recording paused")
            self.cue_detail.config(text="Partial data has been kept. Start the guided step again when ready.")
            self.progress_text.config(text="Incomplete recording — no accuracy result produced.")
        self.refresh_buttons()

    def toggle_control(self):
        if self.menu.armed:
            self.pause()
            return
        if not self.profile or not self.validated or self.protocol_kind or self.analysis_job:
            self.status.config(text="Finish calibration and the fresh-blink check before starting.")
            return
        if not self.is_fresh():
            self.status.config(text="Waiting for two seconds of fresh signals. Try again shortly.")
            return
        self.engine.cancel()
        self.menu.armed = True
        self.mark("control_started", profile=self.profile.to_dict(), highlighted=WORDS[self.menu.index])
        self.cue_title.config(text="Blink control is on")
        self.cue_detail.config(text="Two blinks: move the highlight. Three blinks: speak that word.\nBlink about half a second apart, then wait for the response.")
        self.log_event("Blink control ON.")
        self.refresh_buttons()

    def pause(self, reason="Blink control paused. Pending blinks cleared."):
        if self.protocol_kind or self.analysis_job:
            self.cancel_protocol()
        was_armed = self.menu.armed
        self.menu.pause()
        if self.engine:
            self.engine.cancel()
        self.speaker.cancel_pending()
        if was_armed:
            self.mark("control_paused", reason=reason)
            self.log_event(reason)
            self.cue_title.config(text="Blink control paused")
            self.cue_detail.config(text="Click Start blink control when you are ready to continue.")
        self.status.config(text=reason)
        self.refresh_buttons()

    def audio_changed(self):
        if not self.audio_enabled.get():
            self.speaker.cancel_pending()
        self.mark("audio_setting", enabled=self.audio_enabled.get())

    def pick_word(self, index):
        if self.protocol_kind or self.analysis_job:
            return
        self.menu.index = index
        if self.engine:
            self.engine.cancel()
        self.update_tiles()
        self.spoken.config(text=f"Selected: {WORDS[index]}")
        self.mark("manual_highlight", word=WORDS[index])

    def manual_speak(self):
        if self.protocol_kind or self.analysis_job:
            return
        if self.engine:
            self.engine.cancel()
        self.say(PHRASES[self.menu.index])
        self.mark("manual_speak", word=WORDS[self.menu.index])

    def say(self, phrase):
        self.spoken.config(text=phrase)
        if self.audio_enabled.get():
            if not self.speaker.say(phrase):
                self.status.config(text="Speaker is busy or unavailable. The selected phrase remains on screen.")
                self.mark("speech_not_queued", phrase=phrase)
        else:
            self.status.config(text="Sound is off. Phrase displayed on screen.")

    def inject(self, count):
        if isinstance(self.source, DemoSource) and not self.protocol_kind and not self.analysis_job:
            self.source.inject(count)
            self.mark("practice_injection", count=count)

    def apply_settings(self):
        if not self.profile or self.protocol_kind or self.analysis_job:
            return
        self.pause("Detection settings changed; a new test is required.")
        detail = self.profile.to_dict()
        detail.pop("profile_id")
        detail.update(threshold=self.profile.threshold * self.sensitivity.get(), group_gap=self.group_gap.get(), validation={})
        self.profile = Profile(**detail)
        self.engine.set_profile(self.profile)
        self.validated = False
        self.profile.save(self.profile_path)
        self.writer.artifact(f"profile_{self.profile.profile_id[:8]}.json", self.profile.to_dict())
        self.mark("settings_changed", profile=self.profile.to_dict())
        self.sensitivity.set(1)
        self.readiness.config(text="Settings changed. Test on fresh blinks before starting control.")
        self.profile_summary()
        self.refresh_buttons()

    def profile_summary(self):
        if not self.profile:
            self.profile_detail.config(text="No personal calibration yet.")
            return
        p = self.profile
        self.profile_detail.config(text=f"Active pad: CH{p.channel + 1} / A{p.channel}P\nTrigger: {p.threshold:.3g} filtered native units\nBlink group gap: {p.group_gap:.2f}s\nProfile: {p.profile_id[:12]}\nA new fresh-blink check is required after reconnecting or changing settings.")

    def update_tiles(self):
        for i, tile in enumerate(self.tiles):
            tile.config(bg=BLUE if i == self.menu.index else CARD,
                        fg=BG if i == self.menu.index else TEXT,
                        text=("•  " if i == self.menu.index else "") + WORDS[i])

    def refresh_buttons(self):
        connected = self.meta is not None
        idle = not self.protocol_kind and not self.analysis_job
        for widget, enabled in ((self.scan_button, not self.source and not self.scanning),
                                (self.connect_button, not self.source and bool(self.streams)),
                                (self.demo_button, not self.source and not self.scanning),
                                (self.disconnect_button, self.source is not None),
                                (self.calibrate_button, connected and idle),
                                (self.quick_check_button, connected and idle and self.profile is not None),
                                (self.check_button, connected and idle and self.profile is not None),
                                (self.long_check_button, connected and idle and self.profile is not None),
                                (self.cancel_button, not idle),
                                (self.arm_button, connected and idle and self.validated),
                                (self.pause_button, connected),
                                (self.settings_button, connected and idle and self.profile is not None)):
            widget.config(state="normal" if enabled else "disabled")
        self.arm_button.config(text="Pause blink control" if self.menu.armed else "Start blink control")
        for b in self.demo_inject_buttons:
            b.config(state="normal" if isinstance(self.source, DemoSource) and connected and idle else "disabled")

    def on_chunk(self, chunk):
        if not self.engine:
            return
        now = self.source.clock()
        if not len(chunk.timestamps) or not np.isfinite(chunk.timestamps).all():
            raise ValueError("Missing or invalid sample timestamps.")
        age = float(now - chunk.timestamps[-1])
        if age < -0.2:
            self.mark("unexpected_signal_clock", age_seconds=age)
            raise ValueError(f"Signal clock is {-age:.3f}s ahead of the app. Reconnect to start fresh.")
        if age > 0.5:
            # Retain delayed raw data, but never turn it into menu actions or
            # calibration evidence. Drain the backlog on the existing inlet.
            self.writer.append(chunk.values, chunk.timestamps, chunk.source_timestamps)
            retrying = self.interrupt_guided_step("Signals briefly delayed.")
            if not retrying:
                self.pause("Signals briefly delayed. Control paused; waiting for fresh signals.")
            self.validated = False
            self.engine.reset()
            self.last_data_wall = None
            self.plot.clear()
            self.mark("delayed_chunk", age_seconds=age, samples=len(chunk.timestamps),
                      first_sample_timestamp=float(chunk.timestamps[0]),
                      last_sample_timestamp=float(chunk.timestamps[-1]))
            if not retrying:
                self.readiness.config(text="Delayed signals skipped for control. Wait for fresh signals, then run the fresh-blink test.")
            return
        filtered, blinks, gestures, gaps = self.engine.process(chunk.values, chunk.timestamps)
        self.writer.append(chunk.values, chunk.timestamps, chunk.source_timestamps)
        if chunk.source_timestamps is not None:
            adjustments = chunk.timestamps - chunk.source_timestamps
            changed = int(np.count_nonzero(adjustments))
            if changed:
                self.writer.event("timestamp_adjustment", float(chunk.timestamps[-1]),
                                  samples=changed, max_adjustment_seconds=float(adjustments.max()))
        self.last_data_wall = time.monotonic()
        if gaps:
            retrying = self.interrupt_guided_step("Brief signal delivery gap detected.")
            if not retrying:
                self.pause("Signal gap detected. Blink control paused.")
            self.validated = False
            self.mark("signal_gap", count=gaps)
            if not retrying:
                self.readiness.config(text="Signal gap. Run the fresh-blink test again once the connection is steady.")
            # No events from either side of an interrupted chunk can act.
            gestures = []
        for w in self.windows if self.protocol_kind else []:
            mask = (chunk.timestamps >= w.start) & (chunk.timestamps < w.end)
            if mask.any():
                w.timestamps.extend(chunk.timestamps[mask].tolist())
                w.filtered.extend(filtered[mask].tolist())
        for t, row, raw in zip(chunk.timestamps[::5], filtered[::5], chunk.values[::5]):
            self.plot.append((float(t), row[:2].copy(), raw[:2].copy()))
        recent = [p for p in self.plot if p[0] >= chunk.timestamps[-1] - 1.5]
        if recent and recent[-1][0] - recent[0][0] >= 1.4:
            active = [self.profile.channel] if self.profile else self.selected_channels()
            if active:
                raw_recent = np.asarray([p[2] for p in recent])[:, active]
                tolerance = np.maximum(1.0, np.max(np.abs(raw_recent), axis=0)) * np.finfo(float).eps * 8
                flat = bool(np.all(np.ptp(raw_recent, axis=0) <= tolerance))
                if flat and not self.flat_warning:
                    self.pause("Forehead signal is flat. Check pad and cable contact, then repeat the fresh-blink test.")
                    self.validated = False
                    self.flat_warning = True
                    self.readiness.config(text="Flat forehead signal. Check cables and pads. Recalibrate if needed.")
                    self.mark("flat_signal")
                elif not flat:
                    self.flat_warning = False
                if flat:
                    gestures = []
        if self.profile and self.engine.pulse.start is not None:
            if self.engine.pulse.active_seconds > self.profile.max_width + 0.5:
                self.pause("Signal stayed above the blink level too long. Check the pad contact and relax your face.")
                self.validated = False
                self.cancel_protocol(quiet=True)
                self.readiness.config(text="Sustained signal excursion. Recheck contact and run a fresh-blink test.")
                gestures = []
        for blink in blinks:
            self.writer.event("blink", blink.timestamp, amplitude=blink.amplitude, width=blink.width)
        for g in gestures:
            self.writer.event("gesture", g.timestamp, **{k: v for k, v in asdict(g).items() if k != "timestamp"})
            self.log_event(f"{g.count} blink(s) → {g.command.lower()}" + (" (control paused)" if not self.menu.armed else ""))
            if self.protocol_kind:
                for w in self.windows:
                    if w.start <= g.start and g.timestamp <= w.end:
                        w.gestures.append(g)
                        break
            else:
                action = self.menu.accept(g)
                if action:
                    self.writer.event("menu_action", action["timestamp"], **{k: v for k, v in action.items() if k != "timestamp"})
                    self.update_tiles()
                    if action["action"] == "speak":
                        self.say(action["phrase"])
                    else:
                        self.spoken.config(text=f"Selected: {action['word']}")

    def draw_plot(self):
        if not self.plot:
            return
        self.canvas.delete("all")
        width, height = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
        latest = self.plot[-1][0]
        points = [p for p in self.plot if p[0] >= latest - 8]
        self.plot = deque(points, maxlen=4000)
        channels = min(2, self.meta["channels"]) if self.meta else len(points[-1][1])
        values = np.asarray([p[1] for p in points])
        for ch in range(channels):
            mid = height * (ch + 0.5) / channels
            amplitude = max(1.0, float(np.percentile(np.abs(values[:, ch]), 99)) * 1.3,
                            self.profile.threshold * 1.5 if self.profile and ch == self.profile.channel else 0)
            scale = (height / channels * 0.35) / amplitude
            self.canvas.create_line(0, mid, width, mid, fill=CARD)
            self.canvas.create_text(12, height * ch / channels + 14, text=f"CH{ch + 1} / A{ch}P", fill=MUTED, anchor="w", font=("Segoe UI", 10))
            coords = []
            for t, row, _ in points:
                coords.extend(((t - latest + 8) / 8 * width, mid - row[ch] * scale))
            if len(coords) >= 4:
                self.canvas.create_line(*coords, fill=ACCENT if ch == 0 else BLUE, width=1.5)
            if self.profile and ch == self.profile.channel:
                y = mid - self.profile.polarity * self.profile.threshold * scale
                self.canvas.create_line(0, y, width, y, fill="#e9eef8", dash=(5, 5))
        if self.meta and self.engine:
            self.signal_stats.config(text=f"{self.meta['sample_rate']:g} Hz nominal • {self.writer.count:,} samples recorded • "
                                         + (f"detecting on CH{self.profile.channel + 1}" if self.profile else "not calibrated"))

    def poll(self):
        if self.closing:
            return
        try:
            self._poll()
        except Exception as exc:
            self.log_event(str(exc))
            if self.source:
                self.disconnect(error=str(exc))
            else:
                self.status.config(text=str(exc))
        self.poll_timer = self.root.after(25, self.poll)

    def _poll(self):
        try:
            streams, error = self.scan_results.get_nowait()
            self.scanning = False
            self.streams = streams
            descriptions = [f"{i.name()} | {i.channel_count()}ch | {i.nominal_srate():g}Hz | {i.source_id() or i.uid()[:8]}" for i in streams]
            self.stream_picker["values"] = descriptions
            if streams:
                preferred = next((n for n, i in enumerate(streams) if "npg" in i.name().lower()), 0)
                self.stream_picker.current(preferred)
            self.status.config(text=error or (f"Found {len(streams)} stream(s). Choose yours and connect." if streams else
                               "No LSL stream found. Connect NPG in Chords LSL Connector first, then Scan again."))
            self.refresh_buttons()
        except queue.Empty:
            pass
        if self.source:
            if self.source.error:
                self.disconnect(error=self.source.error)
                return
            # Drain acquisition before checking protocol deadlines; bound one UI
            # callback so drawing and pause controls always get time to run.
            started = time.monotonic()
            while self.source and time.monotonic() - started < 0.035:
                try:
                    kind, value = self.source.messages.get_nowait()
                except queue.Empty:
                    break
                if kind == "ready":
                    self.on_ready(value)
                elif kind == "chunk":
                    self.on_chunk(value)
            if self.last_data_wall and time.monotonic() - self.last_data_wall > 0.75:
                retrying = self.interrupt_guided_step("Signals stopped arriving.")
                if not retrying:
                    self.pause("Signals stopped arriving. Control paused.")
                self.validated = False
                self.last_data_wall = None
                self.engine.reset()
                if not retrying:
                    self.readiness.config(text="Signal stalled. Reconnect, then run the fresh-blink test again.")
            self.advance_protocol()
            if self.meta:
                self.draw_plot()
                if not self.protocol_kind and self.last_data_wall and time.monotonic() - self.last_data_wall < 0.5:
                    self.status.config(text=("PRACTICE • generated signals" if self.meta["simulated"] else "NPG live • recording automatically")
                                       + (" • BLINK CONTROL ON" if self.menu.armed else " • control paused"))
        # Apply background analysis only after draining incoming samples, so a
        # gap or delay can cancel a result before it becomes a usable profile.
        self.collect_analysis_results()
        try:
            while True:
                kind, phrase = self.speaker.results.get_nowait()
                self.log_event(f"{kind}: {phrase}")
                self.mark("speech_" + kind, phrase=phrase)
                if kind == "error":
                    self.audio_enabled.set(False)
                    self.pause("Speaker failed. Blink control paused; selected text is still visible.")
                    self.readiness.config(text=phrase + " Restart the app to retry speech, or use text with sound off.")
        except queue.Empty:
            pass

    def open_recordings(self):
        self.data_root.mkdir(parents=True, exist_ok=True)
        import os
        if hasattr(os, "startfile"):
            os.startfile(str(self.data_root))
        else:
            webbrowser.open(self.data_root.as_uri())

    def close(self):
        if self.closing:
            return
        self.disconnect()
        self.closing = True
        self.root.after_cancel(self.poll_timer)
        self.speaker.close()
        self.root.destroy()

    def callback_error(self, exc_type, exc, traceback):
        self.log_event(f"{exc_type.__name__}: {exc}")
        try:
            self.disconnect(error=str(exc))
        finally:
            self.status.config(text=f"Action could not finish: {exc}. Existing recording files are retained.")


def run(practice=False):
    root = tk.Tk()
    app = Application(root)
    if practice:
        root.after(100, app.practice)
    root.mainloop()
