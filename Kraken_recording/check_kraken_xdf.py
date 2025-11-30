
import os
import numpy as np
import matplotlib.pyplot as plt
import pyxdf
import pandas as pd

# ============
#  CONFIG
# ============

# 🔁 CHANGE THIS to the XDF you want to inspect
XDF_PATH = r"/Users/elodiedong/Desktop/kraken_data/P009/s002/sub-P009_ses-S002_task-Default_run-001_emg_kraken.xdf"

# 🔁 OPTIONAL stim log (set to None if you don’t want to load it)
STIM_LOG_PATH = r"Users/elodiedong/Desktop/kraken_data/P009/s002/stim_log_20251129_211940"
# STIM_LOG_PATH = None


# ============
#  HELPERS
# ============

def find_stream_by_name(streams, name_part):
    """Return first stream whose *name* contains name_part (case-insensitive), or None."""
    name_part = name_part.lower()
    for s in streams:
        name = s["info"]["name"][0].lower()
        if name_part in name:
            return s
    return None


def guess_marker_stream(streams):
    """Try to guess a marker/event stream based on name or type."""
    for s in streams:
        name = s["info"]["name"][0].lower()
        stype = s["info"]["type"][0].lower() if s["info"]["type"] else ""
        if ("marker" in name or "marker" in stype or
                "event" in name or "event" in stype or
                "stim" in name or "trigger" in name):
            return s
    return None


# ============
#  MAIN
# ============

def main():
    # --- Load XDF file ---
    if not os.path.exists(XDF_PATH):
        print(f"❌ XDF file not found:\n{XDF_PATH}")
        return

    print(f"📂 Loading XDF: {XDF_PATH}")
    streams, file_header = pyxdf.load_xdf(XDF_PATH)

    print("\n=== Streams found in file ===")
    for i, s in enumerate(streams):
        name = s["info"]["name"][0]
        stype = s["info"]["type"][0] if s["info"]["type"] else ""
        n_ch = int(s["info"]["channel_count"][0])
        print(f"{i}: name='{name}', type='{stype}', channels={n_ch}")

    # --- Find EMG stream ---
    emg_stream = (find_stream_by_name(streams, "emg")
                  or find_stream_by_name(streams, "kraken")
                  or find_stream_by_name(streams, "muscle"))

    if emg_stream is None:
        print("\n❌ Could not find EMG stream (name containing 'EMG' or 'Kraken').")
        return

    print(f"\n✅ EMG stream selected: '{emg_stream['info']['name'][0]}'")

    # --- Guess marker stream (optional) ---
    marker_stream = guess_marker_stream(streams)
    if marker_stream is not None:
        print(f"✅ Marker stream guessed as: '{marker_stream['info']['name'][0]}'")
    else:
        print("⚠ No obvious marker stream found. We'll just inspect EMG.")

    # --- Extract EMG data ---
    emg_ts = np.asarray(emg_stream["time_stamps"])
    emg_data = np.asarray(emg_stream["time_series"]).astype(float)

    print("\n=== Raw EMG arrays ===")
    print("emg_data shape:", emg_data.shape)
    print("emg_ts shape  :", emg_ts.shape)

    # Handle different channel layouts
    if emg_data.ndim == 1:
        emg_data = emg_data[:, np.newaxis]  # make (N,) -> (N,1)

    # Pick channel 1 for quick 1D view
    emg_data_1 = emg_data[:, 0]

    # Safety check: not enough samples
    if emg_data_1.size < 2 or emg_ts.size < 2:
        print("\n=== EMG basic info ===")
        print(f"Samples: {emg_data_1.size}")
        print("⚠ Not enough samples to compute duration or sampling rate.")
        print("   → The recording likely stopped very quickly or the stream died.")
    else:
        dt = np.diff(emg_ts)
        good = np.isfinite(dt) & (dt > 0)
        if good.sum() == 0:
            fs = float("nan")
        else:
            fs = 1.0 / np.median(dt[good])

        print("\n=== EMG basic info ===")
        print(f"Samples: {emg_data_1.size}")
        print(f"Duration: {emg_ts[-1] - emg_ts[0]:.2f} s")
        print(f"Approx. sampling rate: {fs:.1f} Hz")
        print(f"Amplitude range: [{emg_data_1.min():.3f}, {emg_data_1.max():.3f}]")
        print(f"Any NaNs? {np.isnan(emg_data_1).any()}")

    # --- Marker info ---
    markers_flat = None
    m_ts = None

    if marker_stream is not None:
        m_ts = np.asarray(marker_stream["time_stamps"])
        m_data = marker_stream["time_series"]
        markers_flat = [row[0] for row in m_data]  # usually 2D

        print("\n=== Marker basic info ===")
        print(f"Number of markers: {len(markers_flat)}")
        uniq = sorted(set(markers_flat))
        print(f"Unique marker values (up to 20): {uniq[:20]}")

    # === PLOTS ===
    if emg_data_1.size >= 2 and emg_ts.size >= 2:
        t0 = emg_ts[0]
        t_rel = emg_ts - t0

        # --- All 6 channels: full recording ---
        if emg_data.shape[1] == 6:
            plt.figure(figsize=(14, 10))
            for ch in range(6):
                ax = plt.subplot(6, 1, ch + 1)
                ax.plot(t_rel, emg_data[:, ch], linewidth=0.5)
                if m_ts is not None:
                    for t in m_ts:
                        ax.axvline(t - t0, alpha=0.08)
                ax.set_ylabel(f"Ch {ch+1}")
                if ch == 0:
                    ax.set_title("All 6 EMG channels (full recording)")
                if ch < 5:
                    ax.set_xticklabels([])
            plt.xlabel("Time (s)")
            plt.tight_layout()

        # --- Channel 1 + triggers just below (shared x-axis) ---
        if m_ts is not None and markers_flat is not None and len(m_ts) > 0:
            codes = [int(c) for c in markers_flat]
            times_rel_mark = m_ts - t0

            fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, 6))

            # Top: EMG channel 1
            ax1.plot(t_rel, emg_data_1, linewidth=0.5)
            ax1.set_ylabel("EMG Ch1 (a.u.)")
            ax1.set_title("EMG channel 1 with triggers below")

            # Bottom: marker codes as points over time
            ax2.scatter(times_rel_mark, codes, s=10)
            ax2.set_xlabel("Time (s)")
            ax2.set_ylabel("Marker code")

            # 👉 If you want to zoom on the first 10s, uncomment:
            # ax1.set_xlim(0, 10)

            plt.tight_layout()

        plt.show()
    else:
        print("\n⚠ Skipping plots because there are fewer than 2 EMG samples.")

    # --- Optional: load stim log CSV ---
    if STIM_LOG_PATH is not None:
        if os.path.exists(STIM_LOG_PATH):
            print(f"\n📂 Loading stim log CSV: {STIM_LOG_PATH}")
            log = pd.read_csv(STIM_LOG_PATH)
            print("Columns:", list(log.columns))
            print("\nFirst 5 rows:")
            print(log.head())
        else:
            print(f"\n⚠ Stim log CSV not found:\n{STIM_LOG_PATH}")


if __name__ == "__main__":
    main()
