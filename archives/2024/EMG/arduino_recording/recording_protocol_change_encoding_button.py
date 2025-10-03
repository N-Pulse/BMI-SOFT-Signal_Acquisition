import os
import time
import csv
import serial
import pandas as pd
import numpy as np
import keyboard
from datetime import datetime

# Setup serial connection (Modify COM port as needed)
SERIAL_PORT = "COM7"  # Change this for your system
BAUD_RATE = 115200

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def record_data(sequence, file_path, nb_channels, duration=3, transition_time=3):
    try:
        # filename = f"{participant}_{hand}_{position}_{sequence}_{timestamp}.csv"
        # file_path = os.path.join(base_folder, filename)

        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=3)
        time.sleep(1)
        ser.flushInput()

        print(f"You will keep each position during {duration} seconds.")
        # time.sleep(1)
        print(f"You will have to press the space while you change position.")
        # time.sleep(1)
        print(f"It is enough time, don't rush...")
        time.sleep(1)
        input(f"Press ENTER to start sequence...")
        countdown()
        
        with open(file_path, mode='w', newline='') as file:
            header = ["Timestamp"]
            for i in range(nb_channels):
                header.append(f"Channel{i+1}")
            header.append("Action1", "Action2")
            writer = csv.writer(file)
            writer.writerow(header)  # Modify headers as needed
            
            print("Waiting for first valid data...")
            first_data = None
            while first_data is None:
                raw_data = ser.readline().decode('utf-8').strip()
                channels = []
                for i in range(nb_channels):
                    channels.append(float(raw_data.split(" ")[i]))
                
                if [isinstance(channel, float) for channel in channels].all():
                # if isinstance(channel1, float) and isinstance(channel2, float):  # Ensure it's valid numeric data
                    first_data = channels

            start_sequence_time = time.time()

            for i in range(len(sequence) - 1):
                print(f"Recording '{sequence[i]}'")
                start_action_time = time.time()
                prompted = False
                transition_started = False

                while True:
                    current_time = round(time.time() - start_sequence_time, 3)
                    data = ser.readline().decode('utf-8').strip()

                    channels = []

                    if not data:
                        continue

                    try:
                        for i in range(nb_channels):
                            channels.append(float(data.split(" ")[i]))
                    except ValueError:
                        continue

                    # Prompt for transition after 2 seconds
                    if not prompted and time.time() - start_action_time > 2:
                        print(f"Press and hold SPACE to transition to '{sequence[i+1]}'...")
                        prompted = True

                    buffer = [current_time]
                    for channel in channels:
                        buffer.append(channel)
                    buffer.append(sequence[i])

                    # Read spacebar state
                    if keyboard.is_pressed('space'):
                        transition_started = True
                        buffer.append(sequence[i+1])
                        writer.writerow(buffer)
                    else:
                        writer.writerow(buffer)
                        if transition_started:
                            print(f"Transition complete. Starting '{sequence[i+1]}'\n")
                            break
        
        ser.close()

        print(f"Data recorded successfully to '{file_path}'")

    except serial.SerialException as e:
        print(f"Error: {e}")
        return

def countdown(n=3):
    for i in range(n, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1)

# def run_sequence(sequence, base_folder, participant, hand, position):
#     timestamp = datetime.now().strftime("%y%m%d%H%M%S")
#     input(f"Press ENTER to start sequence...")
#     countdown()
#     for action in sequence:
#         print(f"Perform '{action}'")
#         countdown()
        
#         # Format filename based on naming convention
#         filename = f"{participant}_{hand}_{position}_{action}_{timestamp}.csv"
#         filepath = os.path.join(base_folder, filename)
#         record_data(filepath)
#         print(f"Recorded '{action}' successfully!\n")



duration=3
transition_time=3

# Load Excel file with sequences
file_path = "EMG_recording_protocol.xlsx"
xls = pd.ExcelFile(file_path)
df_sequences = pd.read_excel(xls, sheet_name="Sequences")
nb_of_sequences = np.shape(df_sequences)[1]

# Extract sequences
sequences = {}
for seq in range(nb_of_sequences):
    sequences[seq]=df_sequences.iloc[:,seq].dropna().tolist()

# sequence_1 = df_sequences.iloc[:, 0].dropna().tolist()
# sequence_2 = df_sequences.iloc[:, 1].dropna().tolist()
# sequence_3 = df_sequences.iloc[:, 2].dropna().tolist()
# sequence_4 = df_sequences.iloc[:, 3].dropna().tolist()

# Nb of channels used
nb_channels = 0
while nb_channels not in range(1, 10):
    nb_channels = input("Enter number of channels")

# User inputs
participant = input("Enter participant initials: ")

hand = 0
while hand not in ['L', 'R']:
    hand = input("Enter which hand (L or R): ").upper()

# position = input("Enter position (1-5): ")

# Create necessary folders
base_folder = os.path.join(os.getcwd(), "data")
# base_folder = os.path.join(os.getcwd(), participant, hand, position)
create_folder(base_folder)

# Choose sequence
print("Select sequence to run:")
print("1 - Single DOF Movements")
print("2 - Hand Poses")
print("3 - Grasps")
print("4 - Simple Gestures")
print("5 - Single DOF")

sequence_choice = 0

while sequence_choice not in range(1,nb_of_sequences+1):
    sequence_choice = int(input("Enter sequence number (1-5): "))

timestamp = datetime.now().strftime("%y%m%d%H%M%S")
filename = f"{participant}_{hand}_ch{nb_channels}_{sequence_choice}_{timestamp}.csv"
file_path = os.path.join(base_folder, filename)

record_data(sequences[sequence_choice-1], file_path, nb_channels, duration, transition_time)

