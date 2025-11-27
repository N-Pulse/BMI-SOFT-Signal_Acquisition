#%%

from psychopy import core, visual, event
from pylsl import StreamInfo, StreamOutlet
import random

def main():
    info = StreamInfo(name='stimulus_stream', type='Markers', channel_count=1,
                      channel_format='int32', source_id='stimulus_stream_001')
    outlet = StreamOutlet(info)  # Broadcast the stream.
    
    markers = {
        'test': [99],
        'start': [88],
        'baseline' : [77],
        'movement1' : [1],
        'movement2' : [2],
        'movement3' : [3],
    }

    win = visual.Window([1000, 800], allowGUI=False, monitor='testMonitor', # [1000, 800]
                         units='deg', color="black")

    # baseline
    base = visual.TextStim(win, text="**baseline**")

    # define movements
    mov1 = visual.TextStim(win, text="**open hand**")
    mov2 = visual.TextStim(win, text="**close hand**")
    mov3 = visual.TextStim(win, text="**movement 3**")

    #  image = visual.ImageStim(win, image="data/IMG_0950.jpg", size=(30, 20), ori=-90)  # Adjust size as needed

    mov_done = visual.TextStim(win, text="Relax. \n\n If ready for the next movement, please press <SPACE>")

    countdown = visual.TextStim(win, text="3", color="white", height=3.0)
    def cd_stim():
        for t in range(3, 0, -1):  # Countdown from 3 to 1
            countdown.text = str(f'{t}')
            countdown.draw()
            core.wait(0.9)
            win.flip() # clears the screen
            core.wait(.1)
        core.wait(1)
        
    def mov_stim(movi, mov_n):
        # show which movement is coming up
        hint = visual.TextStim(win, color="white")
        hint.text = f'Next movement is: \n\n     {movi.text} \n\n Are you ready? Press <SPACE>'
        hint.draw()
        win.flip()
        key_resp()

        # start countdown
        cd_stim()
        
        # send marker for performed movement
        movi.draw()
        win.flip()
        outlet.push_sample(mov_n)
        core.wait(2)
        win.flip()
        core.wait(2)

        # movement done
        mov_done.draw()
        win.flip()
        key_resp()

    def key_resp():
        keys = event.waitKeys(keyList=['space', 'escape'])
        win.flip()
        if 'escape' in keys:
            win.close()
            core.quit()

    # Send triggers to test communication
    for _ in range(5):
        outlet.push_sample(markers['test'])
        core.wait(0.5)

    # Start the recording
    start = visual.TextStim(win, text="To start the recording, hit the record button on labrecorder and press <SPACE>")
    start.draw()
    outlet.push_sample( markers['start'])
    win.flip()
    key_resp()
    
    # Show stimuli -- random order!!
    # Choose 20 times randomly
    # Define the stimuli and markers
    stimuli = [
        (base, markers['baseline']),
        (mov1, markers['movement1']),
        (mov2, markers['movement2'])
    ]
    for _ in range(20):
        stimulus, marker = random.choice(stimuli)  # Randomly select one stimulus and its corresponding marker
        mov_stim(stimulus, marker)

    # mov_stim(mov1, markers['movement1'])

    # mov_stim(mov3, markers['movement3'])

    # mov_stim(mov2, markers['movement2'])

    end = visual.TextStim(win, text="Finished! Thank you")
    end.draw()
    win.flip()
    key_resp()

    win.close()
    core.quit()

if __name__ == "__main__":
    main()

#%%