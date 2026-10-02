"""Streamlit MVP: python -m streamlit run ui/app.py."""

from pathlib import Path
import sys
import json

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
from src.realtime.heldout_demo import create_heldout_replay
from src.twss.speech import Speaker


def create_controller() -> CommandController:
    path = PROJECT_ROOT / "models/csp_lda_s001.joblib"
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    return CommandController(dataset_stream(PROJECT_ROOT / "data"), joblib.load(path))


def render_replay(heldout=False) -> None:
    subject, run = 'S001', None
    if heldout:
        st.subheader('Held-Out Evaluation Demo')
        subject = st.sidebar.selectbox('Subject', [f'S{i:03d}' for i in range(1, 11)], key='heldout_subject')
        run = st.sidebar.selectbox('Held-out run', ['R04', 'R08', 'R12'], key='heldout_run')
        train_runs = '+'.join(r for r in ['R04', 'R08', 'R12'] if r != run)
        st.info(f'{subject}: train {train_runs}; replay only {run}. The saved all-runs model is not used in this mode.')
    else:
        st.subheader('Dashboard')
        st.info('Demonstration only — replay data may include model training data')
    st.caption(f'Source: PhysioNet EEGMMIDB dataset replay | Mode: {"held-out evaluation" if heldout else "standard demonstration"} | Model: CSP(4) + LDA')

    threshold = st.sidebar.slider("Confidence threshold", 0.0, 1.0, 0.70, 0.01, key="threshold")
    debug = st.sidebar.checkbox("Debug Mode", value=False, key="debug")
    audio = st.sidebar.checkbox("Enable speech", value=False, key="audio")
    st.sidebar.caption("Speech plays on the computer running this app, only when Speak is clicked.")
    st.sidebar.caption("Below threshold: UNKNOWN, with no word, sentence, or audio.")

    try:
        mode_key = (heldout, subject, run)
        def controller_factory():
            if heldout:
                model, trials = create_heldout_replay(PROJECT_ROOT / 'data', subject, run)
                return CommandController(trials, model)
            return create_controller()
        if "controller" not in st.session_state or st.session_state.get('mode_key') != mode_key:
            st.session_state.controller = controller_factory()
            st.session_state.mode_key = mode_key
            st.session_state.status = "Ready — press Start Command."
            st.session_state.applied_threshold = threshold
        controller = st.session_state.controller
        if st.sidebar.button("Reset replay", key="reset"):
            controller = controller_factory()
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
        if debug or heldout:
            st.write(f"Actual dataset label: {LABEL_NAMES.get(latest.trial.actual_label, 'UNKNOWN')}")
            st.caption(f"Source: {latest.trial.source}")
    else:
        st.caption("Press Start Command to view the six-channel EEG window.")


def render_results(comparison=False):
    st.subheader('Model Comparison' if comparison else 'Evaluation')
    directory = 'phase2_reproduction' if comparison else 'phase1'
    path = PROJECT_ROOT / 'results' / directory / 'results.json'
    if not path.exists():
        st.warning('Results have not been generated yet.'); return
    payload = json.loads(path.read_text(encoding='utf-8'))
    frame = pd.DataFrame(payload['folds'])
    st.caption(f'Stored report: results/{directory}/results.json | Within-subject leave-one-run-out | S001–S010')
    st.info('Metrics use held-out runs. Standard Dashboard predictions are not included in this evaluation.')
    keys = ['model_id', 'subject'] if comparison else ['subject']
    table = frame.groupby(keys)[['accuracy', 'balanced_accuracy', 'f1', 'mcc']].mean().reset_index()
    st.dataframe(table, hide_index=True, width='stretch')
    if comparison:
        aggregate = frame.groupby('model_id')[['accuracy', 'balanced_accuracy', 'f1', 'mcc']].agg(['mean', 'std'])
        st.dataframe(aggregate, width='stretch')
        st.bar_chart(frame.groupby('model_id').accuracy.mean(), y_label='Mean held-out accuracy')
        st.caption('Model and parameter selection on these folds is exploratory; it is not independent confirmation of a winner.')
    else:
        st.bar_chart(table.set_index('subject').accuracy, y_label='Mean held-out accuracy')
        st.caption('Frozen baseline: 64.67% mean accuracy over 30 folds; S001: 68.89%. SD over folds describes variability, not a confidence interval.')
    st.caption('F1 uses LEFT as the positive class. Confusion rows are actual; columns predicted; LEFT=1, RIGHT=2.')
    with st.expander('Per-run metrics and confusion counts'):
        st.dataframe(frame, hide_index=True, width='stretch')


def main() -> None:
    st.set_page_config(page_title='TWSS | BCI Research', page_icon='🧠', layout='wide')
    st.markdown('<style>.stApp {background-color:#f5f8fb;} h1,h2,h3 {color:#173b51;} div[data-testid="stMetric"] {background:white;padding:16px;border-radius:8px;border:1px solid #dde5eb;} </style>', unsafe_allow_html=True)
    st.title('TWSS · EEG to speech')
    st.caption('Motor imagery communication · Phase 1 research MVP')
    page = st.sidebar.radio('Navigation', ['Dashboard', 'Held-Out Demo', 'Evaluation', 'Model Comparison', 'Research / About'], key='navigation')
    if page in ['Dashboard', 'Held-Out Demo']:
        render_replay(page == 'Held-Out Demo')
    elif page in ['Evaluation', 'Model Comparison']:
        render_results(page == 'Model Comparison')
    else:
        st.subheader('Research / About')
        st.write('TWSS maps two motor-imagery decisions to a small communication vocabulary: LEFT → YES → “Yes.”; RIGHT → NO → “No.”')
        st.write('Completed: dataset replay, CSP+LDA, confidence rejection, optional speech and held-out evaluation. Experimental: montage, band, threshold, Riemannian and representation analyses.')
        st.write('UNKNOWN means the classifier confidence did not meet the threshold. It is not a learned REST class.')
        st.write('Hardware operation and useful communication with a new user remain unverified. The system does not read arbitrary thoughts or decode unrestricted speech.')
        st.caption('Technical documentation: docs/TWSS_TECHNICAL_OVERVIEW.md · Literature: docs/LITERATURE_REVIEW.md · Experiments: results/')


if __name__ == "__main__":
    main()
