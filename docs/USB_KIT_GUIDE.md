# USB-first Beast integration guide

Prepared 2026-10-02 for the six-channel NPG Lite Beast with VibZ+.
This is the next-session guide; physical hardware has not been tested here.

## First session: see six signals

1. Confirm the box says NPG Lite and the playmate says VibZ+. Follow the manufacturer's electrode preparation and connection instructions for your board revision.
2. Connect a USB data cable. Use the official NPG Lite Flasher if the device does not already have compatible firmware: choose the **Serial/USB firmware for your NPG Lite/VibZ+ configuration**, not a Bluetooth-only build. Follow the flasher's reconnect instructions.
3. Install the Windows release of **Chords LSL Connector**. Click **Serial**, connect, and check that its graph and sample counter advance with six channels. Close Arduino Serial Monitor, the flasher, and any web serial viewer before connecting; two programs cannot own the same serial port.
4. Leave the connector running. In a PowerShell terminal at `D:\EOTF-TWSS`, run:

```powershell
.venv/Scripts/python.exe -m src.acquisition.list_lsl
```

5. Copy the actual stream name/source ID from that output. Run:

```powershell
.venv/Scripts/python.exe -m src.acquisition.check_lsl --stream-name "YOUR_STREAM_NAME" --source-id "YOUR_SOURCE_ID" --seconds 3
```

Replace both placeholders with detected values. Omit `--source-id` if the publisher has no ID and the name uniquely identifies it. The connector documentation mentions `UDL` for USB; our code intentionally does not assume that name. Multiple matches require explicit selection.

Expected: six channels, a positive metadata sampling rate, finite samples, a window with `round(3 * sampling_rate)` columns, and approximately three seconds of timestamps. `classification: not attempted` is intentional. These values have not yet been observed on your kit.

## Electrode order and units

Our intended scalp locations, following the established model order, are:

| Stream channel (verify actual connector order) | Intended scalp location |
|---|---|
| 1 / A0P | FC3 |
| 2 / A1P | FC4 |
| 3 / A2P | C3 |
| 4 / A3P | C4 |
| 5 / A4P | CP3 |
| 6 / A5P | CP4 |

This is a project placement plan, not proof of the publisher's channel order. Confirm the channel-to-pin mapping before naming a recording. Use an appropriate EEG placement method/cap to locate these positions; labeling arbitrary skin electrodes FC3/C3 does not recreate the training montage. Connect CN/shared negative and REF according to the manufacturer's wiring guide; they are separate connections, not interchangeable names.

`BeastStreamer` preserves native publisher numbers. A label such as CH1 is not a verified scalp location, and `unknown` units are not volts. Document firmware, ADC resolution, sampling rate, analog gain, channel order, reference arrangement and publisher scaling. Confirm the correct conversion to volts from the firmware/connector and hardware specification before MNE preprocessing. Do not guess from signal amplitude.

## Second session: save calibration trials

First test the storage workflow without hardware (no real-time waiting):

```powershell
.venv/Scripts/python.exe -m src.acquisition.calibration --simulation --subject-id SIM001 --session-id usb_practice_01 --trials-per-class 2 --seed 0
```

It replays **raw**, label-matched PhysioNet windows and marks every recording as simulated. It is not new participant data and must not be used as such. Use a new session ID on each run.

After verifying physical order and signal quality, collect a small real session:

```powershell
.venv/Scripts/python.exe -m src.acquisition.calibration --subject-id P001 --session-id usb_01 --trials-per-class 5 --stream-name "YOUR_STREAM_NAME" --source-id "YOUR_SOURCE_ID" --channel-names FC3 FC4 C3 C4 CP3 CP4 --seed 0
```

Console cues are REST 2 s → LEFT/RIGHT imagery 4 s → REST 2 s. Imagine moving the cued hand while keeping it still; follow the cue on screen. The runner randomizes a balanced sequence, starts capture at the cue, and saves each validated raw trial after the final rest. Rate comes from LSL metadata; `--sampling-rate` is an optional expected-rate check, not a resampling option. Files are under `data/own/P001/usb_01/`: NPZ samples/timestamps, per-trial JSON, manifest CSV and session status JSON. Existing sessions cannot be overwritten. Partial sessions retain valid saved trials and record a failure.

## Integration work after collection

The unchanged Streamlit UI still replays PhysioNet. Receiving LSL data does **not** connect raw hardware samples directly to its inference controller.

1. Verify six channels, units, rate, timestamp continuity and sustained acquisition; inspect clipping, flat lines, motion and mains interference.
2. Review the first calibration recording with cue times and provenance. Validate signal quality and actual physical channel order.
3. Add a separate live trial adapter: native samples → verified volts → shared preprocessing → correctly timed model-shaped `Trial`. Plan filtering context explicitly: the frozen MNE FIR implementation is offline and cannot simply filter three seconds causally with identical behavior. The training epochs include both endpoints (481 samples at 160 Hz).
4. Evaluate new participant sessions with run/session separation. The S001 PhysioNet model is a demonstration model, not a validated model for a new person/device. Keep any new calibration model and results separate from frozen Phase 1.
5. Only after those checks wire the adapter into the existing controller, then enable gated commands and speech. UNKNOWN remains silent. No REST model or free-thought/sentence decoding is implemented.

## If no stream appears

Check the USB data cable, Windows Device Manager/COM port, compatible Serial firmware, connector's connected status and advancing counter. Close competing serial applications. Ensure the connector is publishing LSL and permit its local discovery through the Windows firewall if blocked. List streams again before changing Python code. Missing streams, wrong channel counts, stalled input and incomplete/gapped windows are explicit failures; the reader does not fabricate samples.

## Manufacturer sources

- [Beast/VibZ+ wiring and kit guide](https://docs.upsidedownlabs.tech/kits/npg-lite-kits/npg-lite-beast/index.html)
- [NPG Lite Flasher](https://docs.upsidedownlabs.tech/software/tools/npg-lite-flasher/index.html)
- [Chords LSL Connector: installation, USB connection and troubleshooting](https://github.com/upsidedownlabs/Chords-LSL-Connector)

Check these instructions against your installed firmware and board revision at the hardware session.
