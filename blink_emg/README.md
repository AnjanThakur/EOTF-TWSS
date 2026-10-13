# Blink to Speak

A separate desktop project for **your NPG Lite Beast**, inside `blink_emg`.
It turns **deliberate eye blinks** into a highlighted word and spoken phrase.
It includes acquisition, guided recordings, personal calibration, fresh-data
checks, local speech, raw-data saving, and offline replay. It has no dependency
on the parent project's code, PhysioNet data, or saved hand-imagery model.

**What is ready:** the complete software flow and its automated tests.
**What needs your board:** real blink calibration and measured reliability.
Computer-generated practice results do not establish real-world accuracy.

The folder name is `blink_emg` as requested. Forehead blink control primarily
uses the eye's electrical signal / ocular artifact (**EOG**); this app is not an
imagined-speech decoder. It uses personal signal thresholds rather than a
pre-trained machine-learning model.

## Start here

On this laptop, **double-click `start.bat` inside this folder**. It uses a local
Python environment if present, otherwise the existing environment one folder
above. Paths containing spaces are supported.

Or run from PowerShell:

```powershell
Set-Location 'D:\Projects\TWSS\EOTF-TWSS\blink_emg'
.\start.bat
```

Try without the board:

```powershell
.\start.bat --practice
```

In practice mode, wait two seconds, click **Start blink control**, then click
**Practice: 2 blinks** or **Practice: 3 blinks**. These buttons generate signals
that go through the actual filter and detector; they do not directly trigger
menu actions. Practice is visibly marked **SYNTHETIC** and saved separately
from your real personal profile.

### Install on another computer / make this folder independent

Install Python 3.10 or newer with Tk support. Then, from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\start.bat
```

`setup.ps1` creates this folder's own `.venv` and installs `requirements.txt`.
The execution-policy option applies to that one process; the script does not
change the machine's execution policy. Installation needs internet access;
ordinary use needs no internet connection.

You can also install this as a normal Python package:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m blink_emg_app
```

Use the source-folder / launcher workflow for recordings to remain beside
this README. A package installed elsewhere stores recordings and profiles in
`blink_emg` under your user home folder. Set the optional `BLINK_EMG_HOME`
environment variable to choose a different data folder.

## Set up your pads and NPG

For the easy **two-forehead-pad** setup, use four pads in total:

| Cable | Place the pad here |
| --- | --- |
| A0P / CH1 | Bare forehead, above your left eyebrow |
| A1P / CH2 | Bare forehead, above your right eyebrow |
| REF | Bony skin behind your left ear |
| CN | Bony skin behind your right ear |

Set the **A0 and A1 common-negative switches toward CN**. With those switches
enabled, leave A0N and A1N empty. Keep the pads from touching each other.

Only using one forehead pad? Put A0P near the centre of the forehead, keep
REF and CN, enable CN for A0, and **uncheck CH2** in the app. Other channels
can remain unused. The app records every stream channel but detects blinks
only on a selected, calibrated forehead channel. It does not treat floating
unused channels as valid signals.

The manufacturer documents one forehead channel for blink communication and
shared CN for multiple channels. The two forehead pads here offer alternative
channels for calibration to compare; they are not a validated thought-decoding
montage or a requirement for accurate blinks.

Use the board's battery and Bluetooth, with **USB unplugged while the pads are
on you**, following the manufacturer's setup instructions.

**Keep your current raw-signal six-channel BLE firmware. No reflash is needed
for this app.** The manufacturer's separate M2W app uses different blink
firmware; its flashing steps are not part of this project's workflow.

## Connect the signal

1. Turn on the battery-powered NPG.
2. Open **Chords LSL Connector**.
3. Choose Bluetooth and connect your NPG device.
4. Keep the connector open. Disconnect Chords Web from the board if it is
   occupying the Bluetooth connection.
5. Open this app and click **Scan for NPG**.
6. Select your NPG stream, normally `NPG-Lite | 6ch | 500Hz`, then **Connect**.
7. Wait two seconds for the filter to settle.

The app reads LSL from the connector; it does not connect directly to COM5
or Bluetooth. If multiple streams exist, select yours explicitly. It supports
one to six numeric channels at a declared regular rate of 80–2000 Hz. Your
current intended setup is six channels at nominal 500 Hz.

Data starts saving as soon as the connection opens. You do not need to press
record in Chords Web, make separate left/right files, or label files manually.

## Teach it your blinks

Click **Start guided calibration**. This takes about **75 seconds**:

1. Relax and blink normally for 20 seconds.
2. The screen repeatedly says **Get ready** and then **Blink ONCE**.
3. Blink once when instructed, then wait. There are eight single-blink rounds.
4. The app compares your selected forehead channels and chooses the clearest
   usable channel, polarity, and amplitude trigger.

Nothing needs to be imagined. Use comfortable blinks and keep your jaw relaxed.
If calibration fails, it gives a reason and keeps the raw recording. Improve
pad contact and repeat. It does not silently substitute simulated signals.

## Check on fresh recordings

For a shorter practice attempt, click **Quick check (45 sec)**. It records
10 seconds of normal blinking, then three double-blink and three triple-blink
groups in mixed order. Open your eyes fully between blinks, about half a second
apart. It shows correct commands and accidental commands without changing your
calibration. This is practice feedback: it does not enable blink control or
replace the full check below. Connection pauses can extend either check.

Click **Test on fresh blinks (1 min)**. This takes about **one minute**:

1. Blink normally for 10 seconds.
2. Try ordinary face movements for 5 seconds, as the screen instructs.
3. Follow four **Blink TWICE** and four **Blink THREE TIMES** instructions in
   mixed order. Space blinks roughly half a second apart. After each group,
   relax and wait for the next instruction.
4. The app checks the new signals with the calibration settings held fixed.
   It does not tune the detector on these test answers.

The result shows correct trials, missed/wrong gestures, extra commands,
accidental commands during ordinary activity, and commands during waiting.
The JSON report also includes per-class counts and a confusion table.

For more evidence, **Longer test (5 min)** on the Words screen uses **20 double
and 20 triple groups**, 60 seconds of normal blinking, and 15 seconds of ordinary
face movements. This takes about 5 minutes 20 seconds. Repeat on another
session/day to check whether contact and fatigue change the result.

Blink control is enabled after a check with:

- At least eight gesture trials (four of each type), and 15 seconds of ordinary
  activity, with at least 80% correctly classified trials (7/8 for this check).
- At least two-thirds correct for each gesture type.
- No extra commands and no commands during ordinary activity or waiting.
- Complete, continuous signal data for the scored windows.

These are transparent personal readiness criteria, **not a promised product
accuracy or evidence of clinical reliability**. A short zero-error recording
does not prove that accidental actions cannot happen over hours.
The one-minute check trades evidence for less effort: it uses fewer trials
and less ordinary activity than the previous two-minute check. The optional
longer test is better suited to evaluating reliability. Reports include the
readiness criteria used to decide whether control can be started.

## Use the word menu

Click **Start blink control** after the check passes.

| Your action | Result |
| --- | --- |
| One blink | No menu action |
| Two blinks | Move to the next highlighted word |
| Three blinks | Speak the highlighted word |
| Four or more blinks in one group | Reject the group |
| Pause button or Escape | Pause and clear pending blinks; cancel guided recording if active |

Words: **Water, Food, Help, Yes, No, Pain**.

The app deliberately waits after the last blink before acting. Otherwise the
first two blinks of a triple could accidentally move the highlight before
selection. At the default setting, the last blink is followed by roughly
0.8 seconds of waiting. Wait for the visible response before the next group.

Clicking a word highlights it. **Speak selected (mouse)** speaks it manually;
this also works while disconnected. **Test speaker** checks sound. With
**Speak words aloud** unchecked, the selected phrase stays on screen silently.
Pausing cancels queued speech; an utterance already playing may finish.

On Windows, the speech worker calls the native SAPI voice synchronously on its
own COM thread, so each phrase finishes before the next begins. Signal reading
and the interface continue while it speaks. Other operating systems use
pyttsx3. Windows speech uses the system's default audio output; the app sets its
voice volume to 100%, but system volume and application mute still apply.

The app starts with blink control paused. Disconnects, stale input, long
signal excursions, flat signals, missing data, and speech errors pause it.
After reconnecting or changing settings, a new fresh-data check is required.

## If detection needs adjusting

First improve pad contact and repeat calibration. In **Settings & files**:

- A lower trigger multiplier detects weaker signals and may admit more noise.
- A higher trigger multiplier rejects more noise and may miss weak blinks.
- The group gap controls how far apart blinks can be and still form one group.

Click **Apply & require a new test**, then run a new fresh-blink check. The
profile gets a new identifier and its earlier validation is no longer usable.
Two forehead channels are alternatives: the detector uses the chosen channel,
not an unverified voting rule across six channels.

## Files and data format

Each connection creates a unique folder under `blink_emg/data/`:

```text
data/20261011T173000Z_ab12cd34/
  samples.csv          Raw native values + timestamps used for detection/replay
  source_timestamps.csv Original clock-corrected LSL times (new LSL sessions)
  events.jsonl         Cues, blinks, gestures, menu actions, pause and speech events
  metadata.json        Source, channels, rate, simulated/live, sample count, status
  calibration.json     Personal profile when calibration completes
  validation.json      Most recent completed fresh-blink test, when present
  quick_check.json     Most recent completed 45-second practice check, when present
  profile_<id>.json    Adjusted profile snapshots, when present
```

`samples.csv` has **one row per sample**:

```csv
timestamp,ch1,ch2,ch3,ch4,ch5,ch6
12345.000,2012,1998,2001,2010,1997,2002
12345.002,2014,1999,2000,2011,1998,2002
```

Values are native stream values, **not assumed volts or microvolts**. Each
session preserves all source channels. A0 corresponds to ch1; A1 to ch2.
Calibration records which forehead channel was actually used. This project
does not label forehead channels FC3/C3 or reuse the old scalp montage.

Timestamps use the LSL local clock with inlet clock synchronization enabled;
practice uses the local monotonic clock. They are seconds, not wall-clock dates.
Cues record software display times; physical screen latency is not measured.

Samples stream to CSV continuously, with a disk checkpoint about once a second.
Events flush as they occur. **Disconnect** or closing the window finalizes the
recording. A forced shutdown may lose the last buffered second; earlier full
CSV rows remain. `status: recording` after restart means an interrupted session,
not a successfully completed one. Do not use an incomplete test as accuracy.

Personal profiles are under `profiles/npg.json` and `profiles/practice.json`.
Profiles and recordings are ignored by Git. Nothing is uploaded by the app.
Events contain the frozen profile for each test, so a later adjustment does
not change what was used for an earlier test.

### Inspect or replay a saved recording

From this folder, using your own environment or the existing parent environment:

```powershell
..\.venv\Scripts\python.exe -m blink_emg_app --inspect '.\data\YOUR_SESSION_FOLDER'
..\.venv\Scripts\python.exe -m blink_emg_app --replay '.\data\YOUR_SESSION_FOLDER'
```

Inspection checks sample rows, duration, timestamp gaps, saved status, and the
saved validation report. Replay runs the last completed quick or full blink check
through the same causal filter and detector using its saved frozen profile.
It does not retrain or overwrite the recording. No completed check → no
invented accuracy score.

Replay reports both the current detector version and the version recorded at
test start. Older recordings predate this version marker and are labelled
`release_refractory_v1`. Rechecking them after a detector change is development
evidence; use a new recording for an independent test of the changed code.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| No LSL streams | Connect in Chords **LSL Connector**, keep it open, then Scan again. Chords Web alone is not an LSL source. |
| Bluetooth fails | Disconnect other software using the board, check battery power, reconnect the connector. |
| Tiny backwards timestamp jumps | The app now tolerates up to 1 ms of overlap without disconnecting. Larger clock jumps still require reconnecting. |
| Signals briefly delayed | A guided run repeats the interrupted instruction after steady input returns. Outside a guided run, control pauses and another fresh-blink check is required. |
| Signal clock is ahead / changed | Reconnect; a clock mismatch is different from a temporary backlog. |
| Calibration cannot separate blinks | Check forehead pad contact, select only connected forehead channels, relax jaw, repeat comfortable single blinks. |
| Triples look like doubles | Blink about half a second apart. Check the log, increase group gap slightly if needed, then run a new test. |
| Extra commands | Improve contact or raise the trigger slightly. Check ordinary face movement and repeat the test. |
| Brief signal gap during a guided step | Relax while the app waits for steady input and repeats only the interrupted instruction. Earlier completed steps are kept. |
| Flat signal / persistent interruption | Check cables, battery and Bluetooth connection. Reconnect if needed. |
| No sound | Check Windows sound output and installed speech voices; try Test speaker. Text remains available. Restart the app after fixing a speech-backend failure. |
| Missing module | Run setup.ps1 and start again. |

The signal plot is useful for troubleshooting; it cannot certify electrode
contact or distinguish every blink from a jaw or head movement by itself.

## Developer notes and verification

```text
blink_emg_app/
  app.py           Tk desktop UI and nonblocking guided workflow
  sources.py       Bounded LSL worker and explicitly synthetic practice source
  detection.py     Causal filter, blink pulses, delayed gesture grouping
  calibration.py   Personal fitting and separate fresh-data scoring
  protocol.py      Guided calibration, quick practice and two fresh-test lengths
  control.py       Armed menu actions and selection cooldown
  speech.py        Local speech worker with Windows COM thread ownership
  storage.py       Continuous raw saving, checkpoints and inspection
  replay.py        Offline fresh-test replay using the frozen profile
  config.py        Validated, versioned profiles and atomic JSON saves
```

The signal path uses a causal second-order Butterworth bandpass from
0.5–12 Hz at the source rate. It preserves filter state across chunks and
initializes from the first sample to suppress offset startup. Calibration
chooses channel, signal polarity, and a threshold using normal activity and
single-blink examples. Polarity avoids counting the opposite return swing
of a filtered blink as another blink. Pulse duration, hysteresis, settling,
refractory time, and grouping are then applied sample by sample.

The current detector (`sample_duration_v3`) measures pulse width, quiet settling
and refractory spacing by sample count at the declared stream rate. Chords
labels can bunch up during delivery; subtracting those labels made some real
blinks look only a few milliseconds long. The filter already uses the declared
regular rate. Pulse timing now uses it too, while preserving original event
timestamps for grouping and cue attribution. Gaps still reset detection; this
does not interpolate missing samples or rewrite recorded timestamps.
Refractory spacing is anchored to the preceding peak rather than added after
the quiet wait. Polarity, pulse-width limits, long-excursion rejection and
command grouping remain active. Correct declared sampling rate and a continuous
stream are required for sample-count timing.

Chords Bluetooth samples can arrive in batches with time labels only a few
microseconds apart. LSL clock correction can occasionally make those labels
repeat or move backwards. The LSL adapter advances an overlapping label to
the next representable time, with a maximum adjustment of 1 ms. It retains
sample values and order, preserves gaps over 100 ms, and rejects larger clock
jumps. It does not reconstruct acquisition times or remove all batch jitter.
`samples.csv` contains the times used for detection and replay. For new LSL
sessions, `source_timestamps.csv` retains every original clock-corrected LSL
time by zero-based sample index; `metadata.json` describes the policy, and
`events.jsonl` records adjustments. These source times may be non-increasing.
Older recordings and practice recordings keep their existing format.

Calibration fitting and fresh-check scoring run in a background worker after
recording finishes. Incoming samples continue to be processed while the result
is calculated. Cancelling or disconnecting discards any pending result. If
samples are over 0.5 seconds old, the app saves their raw values, pauses control,
discards the interrupted guided attempt and waits for two seconds of fresh
input on the same connection before repeating that instruction. Completed
instructions are retained; only complete, uninterrupted attempts are scored.
The event log marks discarded cues and the reports count repeated steps;
offline replay excludes those same discarded attempts. Cancel / Escape still
stops the whole guided run. Delayed samples never trigger words. Outside a
guided run, a gap pauses control and requires another fresh-blink check;
a saved calibration is retained.

The filter and timing values are starting engineering choices, not universal
physiological constants. Actual forehead recordings decide whether they work
for this user. The app cannot recover information from disconnected or poorly
placed electrodes, and deliberate/natural rapid blink patterns can overlap.

Run tests from this folder:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe -m blink_emg_app --check
```

Automated tests cover the complete desktop workflow with synthetic recordings,
raw replay, held-out scoring, inverted signals, chunk boundaries, double/triple
ambiguity, natural singles, four-blink rejection, gaps, stale/flat input,
profile changes, cancellation, automatic cue retries, matching replay after
gaps and delayed chunks, durable recording, actual local LSL transfer,
and speech-worker failure/queue/thread behavior. LSL integration requires local
network permissions; a restricted sandbox may block it. GUI tests require Tk
and a desktop environment. Hardware recordings and human listening are
separate acceptance checks.

Verified during development on Windows with Python 3.14.2, NumPy 2.5.3,
SciPy 1.18.1, pylsl 1.18.2 and pyttsx3 2.99. The local Windows speech engine
reported two installed voices; no real user blink accuracy has been measured.

## Primary references

- [Manufacturer M2W guide](https://docs.upsidedownlabs.tech/software/applications/m2w/index.html): forehead blink communication and double/triple gestures. Its firmware differs from this raw-LSL app.
- [NPG Lite Beast guide](https://docs.upsidedownlabs.tech/kits/npg-lite-kits/npg-lite-beast/index.html): six-channel hardware, positive inputs, shared CN and battery setup.
- [LSL inlet documentation](https://labstreaminglayer.readthedocs.io/projects/liblsl/ref/inlet.html): clock correction, buffering and stream recovery behavior.
