import matplotlib.pyplot as plt
import pandas as pd

def plot_emg_data(file_path):
    # Load the CSV file
    df = pd.read_csv(file_path)
    
    # Ensure correct column names
    if len(df.columns) < 2:
        print("Error: CSV file must have at least two columns (Timestamp and Sensor Data)")
        return
    
    # Extract time and voltage values
    time_values = df.iloc[:, 0]  # First column (Timestamp)
    voltage_values = df.iloc[:, 1]  # Second column (Sensor Data)
    
    # Plot the data
    plt.figure(figsize=(10, 5))
    plt.plot(time_values, voltage_values, label='EMG Signal', color='b')
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (EMG Signal)")
    plt.title("EMG Signal Over Time")
    plt.legend()
    plt.grid()
    plt.show()



file_path = input("File path: ")
plot_emg_data(file_path)
