# EEG/EMG protocol - EMG-only, LSL-only version

# -*- coding: utf-8 -*-
from psychopy import core, visual, event, gui, prefs
import psychopy  # for psychopy.__version__
from pylsl import StreamInfo, StreamOutlet, local_clock
import os, random, re, gc
from collections import OrderedDict
import csv, time
import json

# Prefer stable movie backends (harmless if missing)
prefs.general['moviesLib'] = ['ffpyplayer', 'moviepy', 'avbin']

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Directory with video instructions (adapt if your folder is different)
MEDIA_DIR = os.path.join(SCRIPT_DIR, "data", "videos_measures_720p")

# ----------------------------- Codes -----------------------------
PHASE = {"cue": 1, "prep": 3, "move": 5, "return": 7, "iti": 9}
ARM_CODES = {"Left": 1, "Right": 2}
BASELINE_NAMES = {
    1: "Palm or fist up",
    2: "Palm or fist side",
    3: "Palm or fist down"
}

# ----------------------------- MOVEMENTS (imported) -----------------------------
try:
    from MOVEMENTS_shared import MOVEMENTS
except ImportError as e:
    raise RuntimeError(
        "Could not import MOVEMENTS. Ensure MOVEMENTS_shared.py "
        "is in the same directory and defines MOVEMENTS."
    ) from e

# --- helpers for labels/keys ---
_strip_bl = re.compile(r"\s*\((?:up|side|down)\)\s*$", re.IGNORECASE)


def strip_baseline_suffix(lbl: str) -> str:
    return _strip_bl.sub("", lbl)


def movement_root(key_or_file: str) -> str:
    return re.sub(r"^(?:1_up_|2_side_|3_down_)", "", key_or_file)


# ----------------------------- Markers -----------------------------
# LSL marker encoding: phase, arm, baseline, movement
def make_marker(phase_code: int, arm_code: int, base_code: int,
                move_code: int) -> int:
    """
    LSL marker code:
      marker = phase*10000 + arm*1000 + base*100 + move

    - phase_code: PHASE[...] (1–5)
    - arm_code:   ARM_CODES[...] (1/2)
    - base_code:  baseline_code (1/2/3)
    - move_code:  MOVEMENTS[mkey]["code"]
    """
    return phase_code * 10000 + arm_code * 1000 + base_code * 100 + move_code


def push_event_codes(outlet, arm: str, phase: str,
                     base_code: int, move_code: int) -> int:
    """
    Send an LSL marker on `outlet`.

    Returns
    -------
    lsl_marker : int
        Integer marker = phase*10000 + arm*1000 + base*100 + move.
    """
    phase_code = PHASE[phase]
    arm_code = ARM_CODES[arm]

    lsl_marker = make_marker(phase_code, arm_code, base_code, move_code)
    outlet.push_sample([lsl_marker], timestamp=local_clock())
    return lsl_marker


# ----------------------------- Resting-state ------
# LSL codes for resting-state
REST_CODES = {"eyes_open": 9701, "eyes_closed": 9702}


# ----------------- Functions to Run Task -----------------------------
def _timed_screen(win, draw_callables, seconds):
    clk = core.Clock()
    while clk.getTime() < float(seconds):
        if 'escape' in event.getKeys(['escape']):
            core.quit()
        for d in draw_callables:
            d.draw()
        win.flip()


def record_resting_state(win, outlet, event_log, label_stim, fix_stim,
                         psycho_ver, subject_id, eeg_fs, emg_fs,
                         do_open=True, open_sec=60.0,
                         do_closed=True, closed_sec=60.0):
    """
    Optional resting-state at the very beginning:
      - eyes open (fixation)
      - eyes closed
    Each segment runs only if enabled and duration > 0.
    """

    # --- Eyes OPEN ---
    if do_open and open_sec > 0:
        label_stim.text = "Resting — eyes OPEN (fixate)"
        t_start = local_clock()

        # LSL marker
        lsl_marker = REST_CODES["eyes_open"]
        outlet.push_sample([lsl_marker])

        hw_trigger = None  # no hardware triggers

        _timed_screen(win, [fix_stim, label_stim], float(open_sec))
        t_end = local_clock()
        event_log.append({
            "phase": "rest_open",
            "lsl_t_start": t_start,
            "lsl_t_end": t_end,
            "duration_s": t_end - t_start,
            "lsl_marker": lsl_marker,
            "arduino_trigger": hw_trigger,
            "subject_id": subject_id,
            "block": 0,
            "rep": 1,
            "arm": None,
            "base_code": None,
            "move_code": None,
            "movement_key": None,
            "file": None,
            "psychopy_version": psycho_ver,
            "eeg_fs": eeg_fs,
            "emg_fs": emg_fs,
        })

    # --- Eyes CLOSED ---
    if do_closed and closed_sec > 0:
        closed_label = visual.TextStim(
            win, text="Resting — eyes CLOSED", color="white",
            height=0.035, pos=(0, -0.45)
        )
        t_start = local_clock()

        # LSL marker
        lsl_marker = REST_CODES["eyes_closed"]
        outlet.push_sample([lsl_marker])

        hw_trigger = None  # no hardware triggers

        _timed_screen(win, [closed_label], float(closed_sec))
        t_end = local_clock()
        event_log.append({
            "phase": "rest_closed",
            "lsl_t_start": t_start,
            "lsl_t_end": t_end,
            "duration_s": t_end - t_start,
            "lsl_marker": lsl_marker,
            "arduino_trigger": hw_trigger,
            "subject_id": subject_id,
            "block": 0,
            "rep": 1,
            "arm": None,
            "base_code": None,
            "move_code": None,
            "movement_key": None,
            "file": None,
            "psychopy_version": psycho_ver,
            "eeg_fs": eeg_fs,
            "emg_fs": emg_fs,
        })


# ----------------------------- GUI  -----------------------------
def setup_gui():
    # -1) Subject & acquisition params
    dS = gui.Dlg(title="Participant / Acquisition")
    dS.addField("Subject ID (e.g. sub-001)", "sub-001")
    # EMG-only: you can set this to 500 to match your Arduino
    dS.addField("EMG sampling rate (Hz)", 500)
    dS.addField("Session label (e.g. ses-001)", "ses-009")
    okS = dS.show()
    if not dS.OK:
        core.quit()
    subj_id = str(okS[0]).strip()
    emg_fs = float(okS[1])
    session_label = str(okS[2].strip())
    eeg_fs = None  # no EEG in this setup

    # 0) Resting-state options + Baseline
    d0 = gui.Dlg(title="Experiment Setup — Start Options")
    d0.addText("Resting-state (optional) — runs at the very beginning if enabled:")
    d0.addField("Include eyes OPEN (fixate)?", choices=["Yes", "No"], initial="Yes")
    d0.addField("Eyes OPEN duration (s)", 60.0)
    d0.addField("Include eyes CLOSED?", choices=["Yes", "No"], initial="Yes")
    d0.addField("Eyes CLOSED duration (s)", 60.0)

    d0.addText("")  # spacer
    d0.addText("Choose the baseline orientation:")
    d0.addField("Baseline position",
                choices=[BASELINE_NAMES[1],
                         BASELINE_NAMES[2],
                         BASELINE_NAMES[3]],
                initial=BASELINE_NAMES[2])
    ok0 = d0.show()
    if not d0.OK:
        core.quit()

    # parse resting-state options
    rest_open = (ok0[0] == "Yes")
    rest_open_s = float(ok0[1])
    rest_closed = (ok0[2] == "Yes")
    rest_closed_s = float(ok0[3])

    # parse baseline
    base_choice = ok0[4]
    rev_map = {v: k for k, v in BASELINE_NAMES.items()}
    chosen_baseline = rev_map[base_choice]  # 1/2/3

    # 1) Movements (filtered) in two checkbox pages
    avail = [
        (k, v) for k, v in MOVEMENTS.items()
        if int(v.get("baseline_code", 0)) == int(chosen_baseline)
    ]
    if not avail:
        d = gui.Dlg(title="No videos")
        d.addText(
            f"No movement videos for {BASELINE_NAMES[chosen_baseline]} "
            f"(code={chosen_baseline})."
        )
        d.show()
        core.quit()

    avail.sort(key=lambda kv: strip_baseline_suffix(kv[1]["label"]).lower())
    n = len(avail)
    mid = n // 2 if n > 1 else n

    def movement_page(page_items, title, defaults_yes_budget, offset):
        fields = OrderedDict()
        label_to_key = {}
        for i, (k, v) in enumerate(page_items):
            label = strip_baseline_suffix(v["label"])
            label_to_key[label] = k
            default = (offset + i) < defaults_yes_budget
            fields[label] = default
        dlg = gui.DlgFromDict(
            dictionary=fields, title=title, order=list(fields.keys())
        )
        if not dlg.OK:
            core.quit()
        return {label_to_key[label]: bool(val) for label, val in fields.items()}

    selections = {}
    if mid > 0:
        selections.update(
            movement_page(
                avail[:mid],
                f"Movements (page 1/2) — {BASELINE_NAMES[chosen_baseline]}",
                defaults_yes_budget=6,
                offset=0,
            )
        )
    if mid < n:
        selections.update(
            movement_page(
                avail[mid:],
                f"Movements (page 2/2) — {BASELINE_NAMES[chosen_baseline]}",
                defaults_yes_budget=6,
                offset=mid,
            )
        )

    if not any(selections.values()):
        d = gui.Dlg(title="Nothing selected")
        d.addText("No movements were selected.")
        d.show()
        core.quit()

    # Arms (checkboxes)
    arms_dict = OrderedDict([("Left arm", True), ("Right arm", True)])
    d_arms = gui.DlgFromDict(
        dictionary=arms_dict, title="Experiment Setup — Arms",
        order=list(arms_dict.keys())
    )
    if not d_arms.OK:
        core.quit()
    arms = []
    if arms_dict["Left arm"]:
        arms.append("Left")
    if arms_dict["Right arm"]:
        arms.append("Right")
    if not arms:
        d = gui.Dlg(title="No arms")
        d.addText("No arms selected.")
        d.show()
        core.quit()

    # 2) Timing + design
    d2 = gui.Dlg(title="Experiment Setup — Timing and Design")
    d2.addText("Timing (seconds)")
    d2.addField("Cue dur", 3.0)
    d2.addField("Prep countdown", 3.0)
    d2.addField("Perform dur", 3.0)
    d2.addField("Return dur", 2.0)
    d2.addField("ITI", 2.0)
    d2.addField("Fix before cue", 1.0)
    d2.addField("Countdown before first cue", 0)

    d2.addText("Design")
    d2.addField("# reps per movement", 6)
    d2.addField("Order", choices=["Random", "Ordered"], initial="Random")
    d2.addField("Inter-block fix", 5.0)
    d2.addField("Test LSL pings?", choices=["Yes", "No"], initial="Yes")
    d2.addField("Fullscreen?", choices=["Yes", "No"], initial="Yes")
    ok2 = d2.show()
    if not d2.OK:
        core.quit()

    i = 0
    cue = float(ok2[i])
    prep = float(ok2[i + 1])
    perf = float(ok2[i + 2])
    ret = float(ok2[i + 3])
    iti = float(ok2[i + 4])
    fix = float(ok2[i + 5])
    cdown = float(ok2[i + 6])
    i += 7
    reps = int(ok2[i])
    i += 1
    order = ok2[i]
    i += 1
    ibfix = float(ok2[i])
    i += 1
    test = (ok2[i] == "Yes" or ok2[i] == 0)
    i += 1
    fs = (ok2[i] == "Yes" or ok2[i] == 0)

    return dict(
        subject_id=subj_id, eeg_fs=eeg_fs, emg_fs=emg_fs,
        baseline_code=chosen_baseline,
        incl=selections, arms=arms,
        cue=cue, prep=prep, perf=perf, ret=ret, iti=iti, fix=fix, cdown=cdown,
        reps=reps, order=order, ibfix=ibfix,
        test=test, fs=fs,
        # resting-state config
        rest_open=rest_open,
        rest_open_sec=rest_open_s,
        rest_closed=rest_closed,
        rest_closed_sec=rest_closed_s,
        
        #Session label 
        session_label=session_label,
    )


# ----------------------------- Media resolution -----------------------------
def arm_candidates(basefile, arm):
    s, e = os.path.splitext(basefile)
    a = arm.lower()
    # try arm-suffixed then generic; try common extensions if needed
    bases = [f"{s}_{a}", s]
    exts = [e] if e else []
    for ext in [".mp4", ".mov", ".MP4", ".MOV"]:
        if ext not in exts:
            exts.append(ext)
    return [b + ext for b in bases for ext in exts]


def resolve_media_path(move_key, arm):
    basefile = MOVEMENTS[move_key]["file"]
    for fname in arm_candidates(basefile, arm):
        p = os.path.join(MEDIA_DIR, fname)
        if os.path.exists(p):
            return p
    # If not found, return None (we’ll show a label instead of a video)
    print("video not found:", basefile)
    return None


# ----------------------------- Playback -----------------------------
def play_movie_robust(win, path, overlay_text="", dur=None):
    """
    Create a MovieStim, play it from start, and stop when:
      - movie finishes (status), OR
      - last frame reached / frames stall, OR
      - elapsed time >= dur (if dur specified), else duration + margin.
    """
    # If no path (missing media), show text for requested duration
    if not path or not os.path.exists(path):
        msg = visual.TextStim(
            win, text=overlay_text or "Missing video",
            color="black", height=0.05, pos=(0, -0.45)
        )
        clk = core.Clock()
        while dur is None or clk.getTime() < float(dur):
            if 'escape' in event.getKeys(['escape']):
                core.quit()
            msg.draw()
            win.flip()
        return

    # Create MovieStim
    try:
        stim = visual.MovieStim(win, path, loop=False)
    except Exception:
        # fallback: show label if creation fails
        msg = visual.TextStim(
            win, text=f"Video error:\n{os.path.basename(path)}",
            color="black", height=0.05
        )
        clk = core.Clock()
        while dur is None or clk.getTime() < float(dur):
            if 'escape' in event.getKeys(['escape']):
                core.quit()
            msg.draw()
            win.flip()
        return

    # Optional overlay label (movement/arm)
    overlay = visual.TextStim(
        win, text=overlay_text, color="black",
        height=0.04, pos=(0, -0.45)
    ) if overlay_text else None

    # Try to read metadata
    fps = n_frames = duration = None
    try:
        fps = stim.getMovieFrameRate()
    except Exception:
        pass
    try:
        n_frames = stim.nFrames
    except Exception:
        pass
    try:
        duration = stim.duration
    except Exception:
        pass
    if duration is None and fps and n_frames:
        duration = float(n_frames) / float(fps)

    # Start playback
    try:
        stim.play()
    except Exception:
        pass

    clk = core.Clock()
    margin = 0.3  # extra time past duration if we rely on duration

    # If user passed a fixed dur, cap by dur; otherwise play full clip (auto-detect)
    cap = float(dur) if dur is not None else (
        None if duration is None else duration + margin
    )

    while True:
        if 'escape' in event.getKeys(['escape']):
            core.quit()

        stim.draw()
        if overlay:
            overlay.draw()
        win.flip()

        # A) declared finished
        try:
            if stim.status == visual.FINISHED:
                break
        except Exception:
            pass

        # B) last frame / frames stall
        try:
            fi = stim.frameIndex
            if n_frames is not None and fi >= (n_frames - 1):
                break
        except Exception:
            pass

        # C) cap by time
        if cap is not None and clk.getTime() >= cap:
            break

        # safety
        if clk.getTime() > 300:
            break

    try:
        stim.stop()
    except Exception:
        pass
    stim = None
    gc.collect()
    core.wait(0.05)  # brief settle


# ----------------------------- Countdown -----------------------------
def show_countdown(win, secs, txt_stim):
    if secs < 1:
        return
    for t in range(int(secs), 0, -1):
        if 'escape' in event.getKeys(['escape']):
            core.quit()
        txt_stim.text = str(t)
        txt_stim.draw()
        win.flip()
        core.wait(1.0)


# ----------------------------- Main -----------------------------
def main():
    # LSL outlet once
    info = StreamInfo(name='stimulus_stream', type='Markers', channel_count=1,
                      channel_format='int32', source_id='stimulus_stream_001')
    exp = info.desc().append_child("experiment")
    exp.append_child_value("task", "Upper-limb both arms")
    exp.append_child_value("version", "EMG-only, LSL-only")
    outlet = StreamOutlet(info)

    # Config
    cfg = setup_gui()

    # Single window for the whole run; skip frame-rate measurement
    win = visual.Window(
        fullscr=cfg["fs"], units='height',
        color="black", checkTiming=False
    )

    # UI stims
    fix = visual.TextStim(win, text="+", color="white", height=0.05)
    ready = visual.TextStim(
        win,
        text="Start your LabRecorder now.\n\nRecording will begin shortly.",
        color="white", height=0.035
    )
    endt = visual.TextStim(
        win, text="Finished! Thank you.",
        color="white", height=0.035
    )
    countdown = visual.TextStim(win, text="", height=0.08, color="white")
    label = visual.TextStim(
        win, text="", height=0.04,
        color="white", pos=(0, -0.45)
    )
    retxt = visual.TextStim(
        win, text="Return to Baseline",
        height=0.04, color="white", pos=(0, -0.45)
    )
    instruction_prep = visual.TextStim(
        win,
        text="Movement instruction video (do not perform the movement)",
        color="white", height=0.05
    )
    instruction_move = visual.TextStim(
        win,
        text="Perform the movement synchronized with the video",
        color="white", height=0.05
    )

    # --- event log (per-event rows) ---
    event_log = []
    psycho_ver = psychopy.__version__
    subject_id = cfg["subject_id"]
    eeg_fs = cfg["eeg_fs"]
    emg_fs = cfg["emg_fs"]

    # Build blocks list
    moves = [k for k, v in cfg["incl"].items() if v]
    if not moves or not cfg["arms"]:
        visual.TextStim(
            win, text="No arms/movements selected",
            color="black"
        ).draw()
        win.flip()
        core.wait(2)
        win.close()
        core.quit()

    blocks = [(a, m) for a in cfg["arms"] for m in moves]
    if cfg["order"].lower().startswith("rand"):
        random.shuffle(blocks)

    # Optional LSL test pings
    if cfg["test"]:
        for _ in range(5):
            outlet.push_sample([9999])
            core.wait(0.5)

    # Ready screen
    ready.draw()
    win.flip()
    outlet.push_sample([8888])
    core.wait(1.5)

    # Pre-run global countdown
    if cfg["cdown"] > 0:
        show_countdown(win, cfg["cdown"], countdown)

    # Optional resting-state at experiment start
    if cfg["rest_open"] or cfg["rest_closed"]:
        record_resting_state(
            win=win, outlet=outlet, event_log=event_log,
            label_stim=label, fix_stim=fix,
            psycho_ver=psycho_ver, subject_id=subject_id,
            eeg_fs=eeg_fs, emg_fs=emg_fs,
            do_open=cfg["rest_open"], open_sec=cfg["rest_open_sec"],
            do_closed=cfg["rest_closed"], closed_sec=cfg["rest_closed_sec"]
        )

    # Run blocks
    for bi, (arm, mkey) in enumerate(blocks):
        move_code = MOVEMENTS[mkey]["code"]
        base_code = MOVEMENTS[mkey]["baseline_code"]

        # Resolve best file for this arm (tries *_left/_right then generic)
        media_path = resolve_media_path(mkey, arm)
        nice_label = f"{arm.upper()} — {strip_baseline_suffix(MOVEMENTS[mkey]['label'])}"

        block_name = mkey
        block_name = block_name[2:].replace("_", " ")
        new_block_instruction = visual.TextStim(
            win,
            text=f"New movement block:\n{block_name}",
            color="white", height=0.05
        )
        new_block_instruction.draw()
        win.flip()
        core.wait(4.0)

        # CUE INSTRUCTION
        instruction_prep.draw()
        win.flip()
        core.wait(2.0)  # show 2 seconds (or change duration)

        # Fixation before cue
        if cfg["fix"] > 0:
            label.text = nice_label
            fix.draw()
            label.draw()
            win.flip()
            core.wait(cfg["fix"])

        # CUE
        t_start = local_clock()
        lsl_marker = push_event_codes(outlet, arm, "cue", base_code, move_code)
        play_movie_robust(
            win, media_path, overlay_text=nice_label, dur=cfg["cue"]
        )
        t_end = local_clock()
        event_log.append({
            "phase": "cue",
            "lsl_t_start": t_start,
            "lsl_t_end": t_end,
            "duration_s": t_end - t_start,
            "lsl_marker": lsl_marker,
            "arduino_trigger": None,
            "subject_id": subject_id,
            "block": bi + 1,
            "rep": 0,
            "arm": arm,
            "base_code": base_code,
            "move_code": move_code,
            "movement_key": mkey,
            "file": os.path.basename(media_path) if media_path else None,
            "psychopy_version": psycho_ver,
            "eeg_fs": eeg_fs,
            "emg_fs": emg_fs,
        })

        for r in range(cfg["reps"]):
            event.clearEvents()

            # INSTRUCTION BEFORE MOVE
            instruction_move.draw()
            win.flip()
            core.wait(1.5)  # show for 1.5 sec (adjust as desired)

            # PREP
            t_start = local_clock()
            lsl_marker = push_event_codes(
                outlet, arm, "prep", base_code, move_code
            )
            show_countdown(win, cfg["prep"], countdown)
            t_end = local_clock()
            event_log.append({
                "phase": "prep",
                "lsl_t_start": t_start,
                "lsl_t_end": t_end,
                "duration_s": t_end - t_start,
                "lsl_marker": lsl_marker,
                "arduino_trigger": None,
                "subject_id": subject_id,
                "block": bi + 1,
                "rep": r + 1,
                "arm": arm,
                "base_code": base_code,
                "move_code": move_code,
                "movement_key": mkey,
                "file": os.path.basename(media_path) if media_path else None,
                "psychopy_version": psycho_ver,
                "eeg_fs": eeg_fs,
                "emg_fs": emg_fs,
            })

            # MOVE (full video recommended; set dur=cfg["perf"] for fixed window)
            t_start = local_clock()
            lsl_marker = push_event_codes(
                outlet, arm, "move", base_code, move_code
            )
            play_movie_robust(
                win, media_path, overlay_text=nice_label, dur=None
            )
            t_end = local_clock()
            event_log.append({
                "phase": "move",
                "lsl_t_start": t_start,
                "lsl_t_end": t_end,
                "duration_s": t_end - t_start,
                "lsl_marker": lsl_marker,
                "arduino_trigger": None,
                "subject_id": subject_id,
                "block": bi + 1,
                "rep": r + 1,
                "arm": arm,
                "base_code": base_code,
                "move_code": move_code,
                "movement_key": mkey,
                "file": os.path.basename(media_path) if media_path else None,
                "psychopy_version": psycho_ver,
                "eeg_fs": eeg_fs,
                "emg_fs": emg_fs,
            })

            # RETURN (text only)
            if cfg["ret"] > 0:
                t_start = local_clock()
                lsl_marker = push_event_codes(
                    outlet, arm, "return", base_code, move_code
                )

                fix.draw()
                retxt.draw()
                win.flip()
                core.wait(cfg["ret"])
                t_end = local_clock()
                event_log.append({
                    "phase": "return",
                    "lsl_t_start": t_start,
                    "lsl_t_end": t_end,
                    "duration_s": t_end - t_start,
                    "lsl_marker": lsl_marker,
                    "arduino_trigger": None,
                    "subject_id": subject_id,
                    "block": bi + 1,
                    "rep": r + 1,
                    "arm": arm,
                    "base_code": base_code,
                    "move_code": move_code,
                    "movement_key": mkey,
                    "file": os.path.basename(media_path) if media_path else None,
                    "psychopy_version": psycho_ver,
                    "eeg_fs": eeg_fs,
                    "emg_fs": emg_fs,
                })

            # ITI (send ITI marker if desired)
            if cfg["iti"] > 0:
                push_event_codes(outlet, arm, "iti", base_code, move_code)
                fix.draw()
                win.flip()
                core.wait(cfg["iti"])

        # Inter-block fixation
        if bi < len(blocks) - 1 and cfg["ibfix"] > 0:
            fix.draw()
            win.flip()
            core.wait(cfg["ibfix"])

    # --- save original event log to CSV ---
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_name = f"stim_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    log_path = os.path.join(log_dir, log_name)

    fieldnames = [
        "phase", "lsl_t_start", "lsl_t_end", "duration_s",
        "lsl_marker", "arduino_trigger",
        "subject_id", "block", "rep", "arm", "base_code", "move_code",
        "movement_key", "file", "psychopy_version", "eeg_fs", "emg_fs"
    ]

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(event_log)

    # --- BIDS-style events export (EMG-only) ---
    # Root: Data/raw/<sub>/ses-XXX/eeg-emg/
    bids_root = os.path.join(os.getcwd(), "Data", "raw")
    session_label = cfg["session_label"]
    sub_dir = os.path.join(bids_root, subject_id, session_label, "emg_kraken")
    os.makedirs(sub_dir, exist_ok=True)

    events_base = f"{subject_id}_{session_label}_task_events"
    events_path = os.path.join(sub_dir, events_base + ".tsv")
    events_json_path = os.path.join(sub_dir, events_base + ".json")

    # Compute onset relative to first event
    if event_log:
        t0 = event_log[0]["lsl_t_start"]
    else:
        t0 = 0.0

    # Write events.tsv
    with open(events_path, "w", newline="", encoding="utf-8") as f_ev:
        w_ev = csv.writer(f_ev, delimiter="\t")
        w_ev.writerow([
            "onset", "duration", "trial_type",
            "arm", "base_code", "move_code", "movement_key",
            "block", "rep",
            "lsl_marker", "arduino_trigger"
        ])
        for ev in event_log:
            onset = float(ev["lsl_t_start"] - t0) if ev["lsl_t_start"] is not None else ""
            duration = float(ev["duration_s"]) if ev["duration_s"] is not None else ""
            trial_type = ev["phase"]
            w_ev.writerow([
                onset,
                duration,
                trial_type,
                ev["arm"],
                ev["base_code"],
                ev["move_code"],
                ev["movement_key"],
                ev["block"],
                ev["rep"],
                ev["lsl_marker"],
                ev["arduino_trigger"],
            ])

    # Write events.json (column metadata)
    events_meta = {
        "onset": {
            "Description": "Event onset in seconds, relative to first logged event.",
            "Units": "s"
        },
        "duration": {
            "Description": "Event duration.",
            "Units": "s"
        },
        "trial_type": {
            "Description": "Phase type (rest_open, rest_closed, cue, prep, move, return, iti)."
        },
        "arm": {
            "Description": "Which arm was used (Left, Right, or None)."
        },
        "base_code": {
            "Description": "Baseline orientation code (1: up, 2: side, 3: down)."
        },
        "move_code": {
            "Description": "Canonical movement code, independent of baseline position."
        },
        "movement_key": {
            "Description": "Key from MOVEMENTS dict describing the movement."
        },
        "block": {
            "Description": "Block index (1-based)."
        },
        "rep": {
            "Description": "Repetition index within a block (0 for cue, 1..N for trials)."
        },
        "lsl_marker": {
            "Description": "Integer marker sent over LSL encoding phase, arm, base, movement."
        },
        "arduino_trigger": {
            "Description": "Legacy column; always None in this EMG-only setup."
        }
    }
    with open(events_json_path, "w", encoding="utf-8") as f_ej:
        json.dump(events_meta, f_ej, indent=4)

    # brief on-screen confirmation
    msg = visual.TextStim(
        win,
        text=(
            f"Run summary saved:\n{log_path}\n\n"
            f"Events TSV/JSON saved in:\n{sub_dir}\n\n"
            "Press any key to exit."
        ),
        color="white", height=0.035
    )
    msg.draw()
    win.flip()
    event.waitKeys()

    # End
    endt.draw()
    win.flip()
    outlet.push_sample([8899])
    core.wait(2)
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
