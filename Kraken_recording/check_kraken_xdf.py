#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick checker for Kraken EMG XDF + PsychoPy log.

- Lists streams in the XDF
- Finds EMG + marker stream
- Prints basic stats
- Plots EMG (full + zoom)
- Optionally shows the stim log CSV

Change XDF_PATH and STIM_LOG_PATH below.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import pyxdf
import pandas as pd

# ============
#  CONFIG
# ============

# 🔁 CHANGE THIS to your actual xdf file path
XDF_PATH = r"/Users/elodiedong/Desktop/kraken_data/s011/sub-P005_ses-S012_task-Default_run-001_emg_kraken.xdf"

# 🔁 OPTIONAL: set this to your stim log CSV, or to None if you don't want to load it
STIM_LOG_PATH = r"/Users/elodiedong/Desktop/kraken_data/s011/stim_log_20251129_143144"
# STIM_LOG_PATH = None

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick checker for Kraken EMG XDF + PsychoPy log.

- Lists streams in the XDF
- Finds EMG + marker stream
- Prints basic stats
- Plots EMG (full + zoom) with markers
- Plots all 6 EMG channels (full + zoom)
- Optionally shows the stim log CSV

Change XDF_PATH and STIM_LOG_PATH below.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import pyxdf
import pandas as pd

# ============
#  CONFIG
# ============

# 🔁 CHANGE THIS to the XDF you want to inspect
XDF_PATH = r"/Users/elodiedong/Desktop/kraken_data/s013/sub-P005_ses-S013_task-Default_run-001_emg_kraken.xdf"

# 🔁 OPTIONAL stim log (set to None if you don’t want to load it)
STIM_LOG_PATH = r"/Users/elodiedong/Desktop/kraken_data/s013/stim_log_20251129_153026"
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
    if marker_stream is not None:
        m_ts = np.asarray(marker_stream["time_stamps"])
        m_data = marker_stream["time_series"]
        markers_flat = [row[0] for row in m_data]  # usually 2D

        print("\n=== Marker basic info ===")
        print(f"Number of markers: {len(markers_flat)}")
        uniq = sorted(set(markers_flat))
        print(f"Unique marker values (up to 20): {uniq[:20]}")
    else:
        m_ts = None

    # --- Marker raster plot (timing & codes) ---
    if marker_stream is not None and len(m_ts) > 0:
        import matplotlib.pyplot as plt

        t0 = emg_ts[0]  # align marker times to EMG start
        times_rel = m_ts - t0
        codes = [int(c) for c in markers_flat]

        # Map each unique code to a separate y-level
        uniq_codes = sorted(set(codes))
        code_to_y = {code: i for i, code in enumerate(uniq_codes)}
        y_vals = [code_to_y[c] for c in codes]

        plt.figure(figsize=(12, 4))
        plt.scatter(times_rel, y_vals, s=12)
        plt.yticks(range(len(uniq_codes)), [str(c) for c in uniq_codes])
        plt.xlabel("Time (s)")
        plt.ylabel("Marker code")
        plt.title("Marker raster (codes over time)")
        plt.tight_layout()
        plt.show()



    # === PLOTS ===
    if emg_data_1.size >= 2 and emg_ts.size >= 2:
        t0 = emg_ts[0]
        t_rel = emg_ts - t0

        # --- Full recording, channel 1 + markers ---
        plt.figure(figsize=(12, 4))
        plt.plot(t_rel, emg_data_1, linewidth=0.5)
        if m_ts is not None:
            for t in m_ts:
                plt.axvline(t - t0, alpha=0.15)
        plt.xlabel("Time (s)")
        plt.ylabel("EMG (a.u.)")
        plt.title("Full EMG recording (channel 1)")
        plt.tight_layout()

        # --- First 10 s, channel 1 + markers ---
        plt.figure(figsize=(12, 4))
        plt.plot(t_rel, emg_data_1, linewidth=0.5)
        if m_ts is not None:
            for t in m_ts:
                if 0 <= (t - t0) <= 10:
                    plt.axvline(t - t0, alpha=0.5)
        plt.xlim(0, 10)
        plt.xlabel("Time (s)")
        plt.ylabel("EMG (a.u.)")
        plt.title("EMG + markers (first 10 s)")
        plt.tight_layout()

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

            # --- All 6 channels: first 10 s ---
            mask = t_rel <= 10
            plt.figure(figsize=(14, 10))
            for ch in range(6):
                ax = plt.subplot(6, 1, ch + 1)
                ax.plot(t_rel[mask], emg_data[mask, ch], linewidth=0.5)
                if m_ts is not None:
                    for t in m_ts:
                        if 0 <= (t - t0) <= 10:
                            ax.axvline(t - t0, alpha=0.3)
                ax.set_ylabel(f"Ch {ch+1}")
                if ch == 0:
                    ax.set_title("All 6 EMG channels (first 10 s)")
                if ch < 5:
                    ax.set_xticklabels([])
            plt.xlabel("Time (s)")
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
