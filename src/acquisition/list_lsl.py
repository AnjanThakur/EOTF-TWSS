"""List discoverable LSL streams."""
from src.acquisition.beast_stream import discover_streams


def main():
    try:
        streams = discover_streams(timeout=2)
        if not streams: print("No LSL streams detected.")
        for info in streams:
            print(f"name: {info.name()} | type: {info.type()} | channels: {info.channel_count()} | sampling_rate: {info.nominal_srate()} | source_id: {info.source_id()}")
    except Exception as exc:
        print(f"Error: {exc}"); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
