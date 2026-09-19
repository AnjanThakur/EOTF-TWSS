"""Streamlit MVP: python -m streamlit run ui/app.py."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.train_csp_lda import CHANNELS
import joblib
import numpy as np
import pandas as pd
import streamlit as st
from src.realtime.controller import CommandController
from src.realtime.dataset_stream import dataset_stream
from src.realtime.inference import LABEL_NAMES
from src.twss.speech import Speaker


def create_controller() -> CommandController:
    path = PROJECT_ROOT / "models/csp_lda_s001.joblib"
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    return CommandController(dataset_stream(PROJECT_ROOT / "data"), joblib.load(path))


def main() -> None:
    st.set_page_config(page_title="TWSS | EEG to speech", page_icon="🧠", layout="wide")
    st.title("TWSS · EEG to speech")
    st.caption("Dataset replay · One EEG trial, one possible command")
    st.info("Demo only: these S001 trials were used to train the saved model. Predictions here are not an accuracy evaluation.")

    threshold = st.sidebar.slider("Confidence threshold", 0.0, 1.0, 0.70, 0.01, key="threshold")
    debug = st.sidebar.checkbox("Debug Mode", value=False, key="debug")
    audio = st.sidebar.checkbox("Enable speech", value=False, key="audio")
    st.sidebar.caption("Speech plays on the computer running this app, only when Speak is clicked.")
    st.sidebar.caption("Below threshold: UNKNOWN, with no word, sentence, or audio.")

    try:
        if "controller" not in st.session_state:
            st.session_state.controller = create_controller()
            st.session_state.status = "Ready — press Start Command."
            st.session_state.applied_threshold = threshold
        controller = st.session_state.controller
        if st.sidebar.button("Reset replay", key="reset"):
            controller = create_controller()
            st.session_state.controller = controller
            st.session_state.status = "Ready — replay reset."
        if st.session_state.applied_threshold != threshold:
            controller.refresh_threshold(threshold)
            st.session_state.applied_threshold = threshold

        status = st.empty()
        if st.button("Start Command", type="primary", disabled=controller.exhausted, key="start"):
            status.info("System status: Processing EEG trial…")
            try:
                with st.spinner("Processing one EEG trial…"):
                    controller.process_next(threshold)
                st.session_state.status = "Ready — trial processed."
            except StopIteration:
                st.session_state.status = "Replay complete — reset to start again."
            except Exception as exc:
                st.session_state.status = f"Error — {exc}"
        status.info(f"System status: {st.session_state.status}")
    except Exception as exc:
        st.error(f"System status: Error — {exc}")
        return

    latest = controller.latest
    st.caption(f"Trials processed: {controller.processed}")
    prediction, confidence, word = st.columns(3)
    prediction.metric("Predicted command", latest.prediction.decision if latest else "—")
    value = latest.prediction.confidence if latest else None
    confidence.metric("Confidence", f"{value:.2%}" if value is not None else "—")
    word.metric("Mapped word", latest.word if latest and latest.word else "—")
    st.subheader("Generated sentence")
    st.write(latest.sentence if latest and latest.sentence else "No sentence generated.")

    if st.button("Speak", key="speak", disabled=not (audio and latest and latest.sentence)):
        # Create/use/close on this thread; do not carry a Windows speech engine across reruns.
        speaker = Speaker(enabled=audio)
        try:
            controller.speak_latest(speaker)
            st.success("Sentence spoken.")
        except Exception as exc:
            st.error(f"Speech error: {exc}")
        finally:
            try:
                speaker.close()
            except Exception as exc:
                st.error(f"Speech cleanup error: {exc}")

    st.subheader("Latest EEG window")
    if latest:
        frame = pd.DataFrame(latest.trial.data.T * 1e6, columns=CHANNELS,
                             index=np.arange(latest.trial.data.shape[1]) / 160)
        frame.index.name = "Time (s)"
        st.line_chart(frame, x_label="Time within window (s)", y_label="EEG (µV)", height=360)
        st.caption("FC3 · FC4 · C3 · C4 · CP3 · CP4 | 3-second window | 8–30 Hz")
        if debug:
            st.write(f"Actual dataset label: {LABEL_NAMES.get(latest.trial.actual_label, 'UNKNOWN')}")
            st.caption(f"Source: {latest.trial.source}")
    else:
        st.caption("Press Start Command to view the six-channel EEG window.")


if __name__ == "__main__":
    main()
