"""Read-only LSL connection check; does not classify or change stream units."""
import argparse
import json
import numpy as np
from src.acquisition.beast_stream import BeastStreamer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream-name")
    parser.add_argument("--stream-type")
    parser.add_argument("--source-id")
    parser.add_argument("--seconds", type=float, default=3)
    args = parser.parse_args()
    source = BeastStreamer(stream_name=args.stream_name, stream_type=args.stream_type,
                           source_id=args.source_id)
    try:
        source.start()
        samples = source.get_window(args.seconds)
        print(json.dumps({"sampling_rate": source.sampling_rate,
                          "channel_names": source.channel_names,
                          "channel_units": source.channel_units,
                          "window_shape": list(samples.shape),
                          "finite": bool(np.isfinite(samples).all()),
                          "timestamp_span_seconds": float(np.ptp(source.last_timestamps)),
                          "classification": "not attempted"}, indent=2))
    except (RuntimeError, ValueError, TimeoutError) as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        source.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
