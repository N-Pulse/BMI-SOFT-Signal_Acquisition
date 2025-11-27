#%% 
import time
import uuid
import numpy as np

from matplotlib import pyplot as plt
from mne import set_log_level

from mne_lsl.datasets import sample
from mne_lsl.stream import StreamLSL 

from mne_lsl.player import PlayerLSL as Player

set_log_level("WARNING")

# %% CONNECT TO STREAM - starting from here, it is the same as in the real EEG acquisition!


source_id = uuid.uuid4().hex
fname = sample.data_path() / "sample-ant-raw.fif"
player = Player(fname, chunk_size=200, source_id=source_id).start()
fs = player.info["sfreq"]
interval = player.chunk_size / fs  # in seconds
stream = StreamLSL(bufsize=2, source_id=source_id).connect()
# # Based on rt_topomap.py
# check inputs
# check_type(stream_name, (str,), "stream_name")
# check_type(winsize, ("numeric",), "winsize")
# assert 0 < winsize
# check_type(duration, ("numeric",), "duration")
# assert 0 < duration

# variables
winsize = 3
duration = 30
stream_name = "Gwennie-24"

#%%
#stream = StreamLSL(bufsize=winsize, name=stream_name).connect()
#stream.drop_channels(("TRG", "X1", "X2", "X3", "A2"))
stream.pick("Fp1")
stream.set_montage("standard_1020")
stream.filter(2, 25)
# stream.info

#%%

#%% create feedback

plt.ion()

time.sleep(winsize)

# main loop
start = time.time()

calibration_points, calibration_times = [], []


while time.time() - start < duration:
    data, _ = stream.get_data(winsize)
    calibration_points.append(data)

calibration_points = np.array(calibration_points)
baseline_FP1 = np.mean(calibration_points.ravel())
std_FP1 = np.std(calibration_points)

print(baseline_FP1)

datapoints, times = [], []

while stream.n_new_samples < stream.n_buffer:
    time.sleep(0.1)

while len(datapoints) != 30:
    if stream.n_new_samples == 0:
        continue
    data, _ = stream.get_data(winsize)

    datapoints.append(data)

    # compute metric
    print(data.shape)

    # print(metric)
    time.sleep(0.2)

    plt.plot(np.array(data).ravel())
    plt.hlines(baseline_FP1,0,900,colors="red")
    plt.hlines(baseline_FP1+4*std_FP1,0,900,colors="red")

    blinking = np.abs(data-baseline_FP1) > 4*std_FP1

    plt.hlines(baseline_FP1-4*std_FP1,0,900,colors="red")
    plt.plot(blinking*(baseline_FP1+4*std_FP1), color="black")
    plt.show(block=True)


time.sleep(20)
plt.ioff()
plt.close()

stream.disconnect()

# how to adapt this to real time, next timepoints 