import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime
from pathlib import Path

# --------- CONFIGURE THIS IF NEEDED ---------
DEFAULT_CSV_FILE = "temperature_log_2026-01-19_14-57-29.csv"
TIME_COL = 0  # first column is timestamp
PROBE_COLS = [1, 2, 3, 4, 5, 6]  # 6 probes
THERMISTOR_COL = 7
RELAY_COL = 8
PID_COL = 9
# --------------------------------------------

def load_data(csv_path: str) -> pd.DataFrame:
    """
    Load CSV with header row, parse timestamp into datetime.
    """
    # Read CSV with header (skip=0 is default)
    df = pd.read_csv(csv_path)

    # Parse time column (handles various timestamp formats)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format='mixed', utc=False)

    # Rename columns for consistency
    df = df.rename(columns={
        "Timestamp": "time",
        "Probe 11": "probe_1",
        "Probe 13": "probe_2",
        "Probe 22": "probe_3",
        "Probe 21": "probe_4",
        "Probe 12": "probe_5",
        "Probe 23": "probe_6",
        "Heater Thermistor": "thermistor",
        "Heater Relay": "relay",
        "PID Output": "pid_output"
    })

    # Map relay On/Off to 1/0 for plotting
    df["relay_state"] = df["relay"].map({"On": 1, "Off": 0})
    return df


def plot_graphs(df: pd.DataFrame, save_prefix: str = "temperature_plots"):
    """
    Create two graphs:
      1) Time vs 6 probes + thermistor
      2) Time vs thermistor, relay state, PID output
    """
    # Common X axis
    x = df["time"]

    # Nice date formatter for x-axis
    date_fmt = DateFormatter("%H:%M:%S")

    # ---------------- Graph 1 ----------------
    fig1, ax1 = plt.subplots(figsize=(12, 6))

    probe_colors = [
        "tab:blue",
        "tab:orange",
        "tab:green",
        "tab:red",
        "tab:purple",
        "tab:brown",
    ]

    for i in range(6):
        col_name = f"probe_{i+1}"
        ax1.plot(
            x,
            df[col_name],
            label=f"Probe {i+1}",
            color=probe_colors[i % len(probe_colors)],
            linewidth=1.2,
        )

    # Add thermistor
    ax1.plot(
        x,
        df["thermistor"],
        label="Heater Thermistor",
        color="black",
        linewidth=1.5,
        linestyle="--",
    )

    ax1.set_xlabel("Time")
    ax1.set_ylabel("Temperature (°C)")
    ax1.set_title("Probe Temperatures and Thermistor vs Time")
    ax1.legend(loc="best")
    ax1.grid(True, linestyle="--", alpha=0.3)

    ax1.xaxis.set_major_formatter(date_fmt)
    fig1.autofmt_xdate()

    # Save JPG
    jpg1 = f"{save_prefix}_probes_thermistor.jpg"
    fig1.savefig(jpg1, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {jpg1}")

    # ---------------- Graph 2 ----------------
    fig2, ax2 = plt.subplots(figsize=(12, 6))

    # Thermistor temperature
    ax2.plot(
        x,
        df["thermistor"],
        label="Thermistor (°C)",
        color="tab:blue",
        linewidth=1.5,
    )
    ax2.set_xlabel("Time")
    ax2.set_ylabel("Temperature (°C)", color="tab:blue")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    # Second Y-axis for PID output
    ax2b = ax2.twinx()
    ax2b.plot(
        x,
        df["pid_output"],
        label="PID Output",
        color="tab:orange",
        linewidth=1.5,
    )
    ax2b.set_ylabel("PID Output", color="tab:orange")
    ax2b.tick_params(axis="y", labelcolor="tab:orange")

    # Relay state as step plot (scaled for visibility)
    relay_scaled = df["relay_state"] * 10.0
    ax2b.step(
        x,
        relay_scaled,
        where="post",
        label="Heater Relay (On=10, Off=0)",
        color="tab:green",
        linewidth=1.2,
        alpha=0.7,
    )

    ax2.set_title("Thermistor, Heater Relay State, and PID Output vs Time")
    ax2.grid(True, linestyle="--", alpha=0.3)

    ax2.xaxis.set_major_formatter(date_fmt)
    fig2.autofmt_xdate()

    # Build a combined legend (from both axes)
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="best")

    # Save JPG
    jpg2 = f"{save_prefix}_thermistor_pid_relay.jpg"
    fig2.savefig(jpg2, dpi=300, bbox_inches="tight")
    print(f"✓ Saved: {jpg2}")

    plt.show()


def main():
    # Get CSV filename from command line or use default
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = DEFAULT_CSV_FILE

    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path.resolve()}")
        sys.exit(1)

    print(f"📂 Loading: {csv_path.name}")
    try:
        df = load_data(str(csv_path))
        print(f"✓ Loaded {len(df)} data points\n")
        
        print("📊 Generating graphs...")
        plot_graphs(df)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
