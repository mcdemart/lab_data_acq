# %%
import os
import glob
import pandas as pd
# Skip first 22 rows when reading CSV
import matplotlib.pyplot as plt

# Directory containing CSV files
csv_dir = r"C:\Users\photonics\Documents\Thorlabs\Optical Power Monitor"
csv_files = glob.glob(os.path.join(csv_dir, "*.csv"))

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file, skiprows=22)
        # Try to find columns for time and power
        time_col = None
        power_col = None

        # Check for time and power columns
        print(df.columns)
        for col in df.columns:
            if 'time' in col.lower():
                time_col = col
            if 'power' in col.lower():
                power_col = col
        if time_col is None or power_col is None:
            print(f"Could not find time/power columns in {csv_file}")
            continue
        # Convert time column to seconds from ms
        
        print(f"Converting {time_col} from milliseconds to seconds in {csv_file}")
        # Convert time from milliseconds to seconds
        df[time_col] = df[time_col] / 1000.0  # Convert milliseconds to seconds
        
        # convert power to uw from W
        df[power_col] = df[power_col] * 1e6  # Convert Watts to microWatts

        plt.figure()
        plt.plot(df[time_col], df[power_col])
        plt.xlabel("Time (s)")
        plt.ylabel("Power (uW)")
        plt.title(f"Measured Power vs Time\n{os.path.basename(csv_file)}")
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Error processing {csv_file}: {e}")
# %%
