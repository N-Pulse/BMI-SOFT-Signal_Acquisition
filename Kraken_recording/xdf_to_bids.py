import os
import json
import numpy as np
import pyxdf
import mne
from mne.export import export_raw

# ========= USER PARAMETERS (adapt these) =========
XDF_PATH = r"/Users/elodiedong/Desktop/kraken_data/s011/sub-P005_ses-S011_task-Default_run-001_emg_kraken.xdf"
BIDS_ROOT = r"/Users/elodiedong/Desktop/kraken_data/BIDS"   # where you want the BIDS dataset

SUBJECT = "P005"   # or "005" if you prefer
SESSION = "S011"   # or "012"
TASK = "Default"
RUN = "01"
LINE_FREQ = 50.0   # or 50 in europe 
# =================================================

print(f"Loading XDF: {XDF_PATH}")
streams, file_header = pyxdf.load_xdf(XDF_PATH)

print("\n=== Streams found in file ===")
for i, s in enumerate(streams):
    name = s["info"]["name"][0]
    stype = s["info"]["type"][0] if s["info"]["type"] else ""
    n_ch = int(s["info"]["channel_count"][0])
    print(f"{i}: name='{name}', type='{stype}', channels={n_ch}")

# ---- Find EMG stream (by name containing 'EMG') ----
def find_stream(name_part):
    for s in streams:
        if name_part.lower() in s["info"]["name"][0].lower():
            return s
    return None

emg_stream = find_stream("EMG")
if emg_stream is None:
    raise RuntimeError("Could not find a stream with 'EMG' in its name!")

emg_name = emg_stream["info"]["name"][0]

# --- Robust sampling frequency extraction ---
info_dict = emg_stream["info"]

def _unpack(val):
    """Handle values that can be scalar, list, tuple, or numpy array."""
    import numpy as np
    if isinstance(val, (list, tuple)):
        return val[0] if len(val) > 0 else None
    if isinstance(val, np.ndarray):
        return val[0] if val.size > 0 else None
    return val

def _has_value(val):
    """Return True if val is non-empty / non-null."""
    import numpy as np
    if val is None:
        return False
    if isinstance(val, (list, tuple)):
        return len(val) > 0 and val[0] not in ("", None)
    if isinstance(val, np.ndarray):
        return val.size > 0
    if isinstance(val, str):
        return val != ""
    return True  # numbers etc.

sfreq_field = info_dict.get("effective_srate", None)

if _has_value(sfreq_field):
    sfreq_raw = _unpack(sfreq_field)
else:
    sfreq_raw = _unpack(info_dict.get("nominal_srate", None))

if sfreq_raw is None:
    raise RuntimeError("Could not determine sampling frequency from XDF (no effective_srate or nominal_srate).")

sfreq = float(sfreq_raw)
print(f"Detected sampling frequency: {sfreq} Hz")

data = np.asarray(emg_stream["time_series"])  # shape (n_samples, n_channels)

data = data.T  # -> (n_channels, n_samples)

n_channels, n_samples = data.shape
print(f"\n✅ Using EMG stream '{emg_name}' with {n_channels} channels @ {sfreq} Hz")
print(f"   Data shape: {data.shape} (n_channels, n_samples)")

# ---- Create MNE Raw object (channels marked as EMG) ----
ch_names = []
for ch in range(n_channels):
    # if channel labels exist in XDF, use them; otherwise EMG1, EMG2, ...
    try:
        ch_label = emg_stream["info"]["desc"][0]["channels"][0]["channel"][ch]["label"][0]
    except Exception:
        ch_label = f"EMG{ch+1}"
    ch_names.append(ch_label)

ch_types = ["emg"] * n_channels
info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)
info["line_freq"] = LINE_FREQ

raw = mne.io.RawArray(data, info)

# ---- BIDS paths ----
sub = f"sub-{SUBJECT}"
ses = f"ses-{SESSION}"

emg_dir = os.path.join(BIDS_ROOT, sub, ses, "emg")
beh_dir = os.path.join(BIDS_ROOT, sub, ses, "beh")
os.makedirs(emg_dir, exist_ok=True)
os.makedirs(beh_dir, exist_ok=True)

bids_basename = f"sub-{SUBJECT}_ses-{SESSION}_task-{TASK}_run-{RUN}"

bv_fname = bids_basename + "_emg.vhdr"
bv_path = os.path.join(emg_dir, bv_fname)

print(f"\n💾 Writing EMG to BrainVision: {bv_path}")
export_raw(bv_path, raw, fmt="brainvision", overwrite=True)


# ---- Sidecar JSON for EMG ----
emg_json = {
    "TaskName": TASK,
    "Device": "Kraken / EMG system via LSL",
    "SamplingFrequency": sfreq,
    "PowerLineFrequency": LINE_FREQ,
    "EMGChannelCount": int(n_channels),
    "EMGChannelNames": ch_names,
    "Manufacturer": "Unknown",
    "ManufacturerModelName": "Unknown",
    "RecordingType": "continuous",
    "Demeaned": False,
    "Reference": "unknown",
}

emg_json_path = os.path.join(emg_dir, bids_basename + "_emg.json")
print(f"💾 Writing EMG sidecar JSON: {emg_json_path}")
with open(emg_json_path, "w") as f:
    json.dump(emg_json, f, indent=4)

# ---- Minimal dataset_description.json (if not present) ----
dataset_description_path = os.path.join(BIDS_ROOT, "dataset_description.json")
if not os.path.exists(dataset_description_path):
    dataset_description = {
        "Name": "Kraken EMG dataset",
        "BIDSVersion": "1.9.0",
        "DatasetType": "raw",
        "Authors": ["Elodie", "Lab team"],
    }
    print(f"💾 Creating dataset_description.json at {dataset_description_path}")
    with open(dataset_description_path, "w") as f:
        json.dump(dataset_description, f, indent=4)
else:
    print("dataset_description.json already exists, leaving it unchanged.")

print("\n✅ Done. EDF + JSON have been written in BIDS structure.")
print("   Next step: move/rename your events.tsv + events.json into the 'beh/' folder.")
