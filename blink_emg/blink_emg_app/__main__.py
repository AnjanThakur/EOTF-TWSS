"""Launch the desktop app or inspect a saved session."""
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Blink to Speak — local NPG Lite forehead-blink communication")
    parser.add_argument("--practice", action="store_true", help="Start with computer-generated signals (no hardware accuracy claim)")
    parser.add_argument("--inspect", metavar="SESSION_FOLDER", help="Inspect a saved recording and its fresh-data report without opening the GUI")
    parser.add_argument("--replay", metavar="SESSION_FOLDER", help="Re-evaluate the last completed quick or full blink check from saved raw samples")
    parser.add_argument("--check", action="store_true", help="Check Python dependencies without connecting to hardware or playing speech")
    args = parser.parse_args()
    try:
        if args.check:
            import tkinter
            import numpy
            import scipy
            import pylsl
            import pyttsx3
            if sys.platform == "win32":
                import pythoncom
                import win32com.client
            print(f"Python {sys.version.split()[0]} | Tk {tkinter.TkVersion} | NumPy {numpy.__version__} | SciPy {scipy.__version__} | LSL {pylsl.__version__}")
            print("Dependencies available. A real blink recording is still needed to check hardware detection.")
        elif args.replay:
            from .replay import replay_validation
            print(json.dumps(replay_validation(args.replay), indent=2, allow_nan=False))
        elif args.inspect:
            from .storage import inspect_session
            print(json.dumps(inspect_session(args.inspect), indent=2, allow_nan=False))
        else:
            from .app import run
            run(practice=args.practice)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"Blink to Speak: {exc}\nRun setup.ps1 in the blink_emg folder if dependencies are missing.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
