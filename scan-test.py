"""
Arduino scan program (serial COM3, 115200)
- Put your scan parameters at the top (Area, center, speed, delay)
- Script performs startup -> scanning (with live heatmap) -> return to center
- Requirements: pyserial, numpy, matplotlib
    pip install pyserial numpy matplotlib
"""

import serial
import time
import re
import numpy as np
import matplotlib.pyplot as plt
import math
import sys

# ----------------------------
# User parameters (top of file)
# ----------------------------
PORT = "COM3"
BAUDRATE = 115200

Area = 5                    # integer: grid will be Area x Area

center = [0, 0]              # [x, y] integer. Default: current position (xPos,yPos start at 0)
speed = 1000                  # single int for both motors
delay_ms = 100                # delay (tau) in ms between stopping and ADC read

# ----------------------------
# Internal / constants
# ----------------------------
READ_TIMEOUT = 2.0           # seconds - serial read timeout for waiting replies
ACK_TEXT = "OK"             # expected acknowledgement text from Arduino after a move
ADC_RE = re.compile(r"ADC:\s*([-+]?\d+)")   # adjust if ADC format differs

# Current position variables (relative coordinates, start at 0)
xPos = 0
yPos = 0

# Flag whether we had any previous measurement (for plot creation)
measurement_done = False

# ----------------------------
# Serial helper functions
# ----------------------------
def open_serial(port=PORT, baud=BAUDRATE, timeout=0.2):
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
        # small delay for Arduino auto-reset
        time.sleep(2.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"[serial] Opened {port} @ {baud}")
        return ser
    except Exception as e:
        print(f"[serial] ERROR opening serial: {e}")
        sys.exit(1)

def send_command(ser, cmd, end="\n"):
    full = f"{cmd}{end}"
    ser.write(full.encode("utf-8"))
    ser.flush()
    print(f">>> {cmd}")

def read_line(ser, timeout=READ_TIMEOUT):
    """
    Wait up to 'timeout' seconds for a non-empty line from serial.
    Returns the stripped line or None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = ser.readline()
            if not line:
                continue
            try:
                s = line.decode("utf-8", errors="replace").strip()
            except:
                s = str(line)
            if s == "":
                continue
            print(f"<<< {s}")
            return s
        except Exception as e:
            print(f"[serial] read exception: {e}")
            return None
    return None

def wait_for_ack(ser, timeout=READ_TIMEOUT):
    """
    Wait for an acknowledgement line that contains ACK_TEXT.
    Returns True if ACK seen, False on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = read_line(ser, timeout=deadline - time.time())
        if line is None:
            break
        if ACK_TEXT in line:
            return True
        # ignore other lines here
    return False

def wait_for_adc_value(ser, timeout=READ_TIMEOUT):
    """
    Wait for a line matching ADC_RE and return integer value.
    Calls read_line repeatedly until it finds a valid ADC line or times out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = read_line(ser, timeout=deadline - time.time())
        if line is None:
            break
        m = ADC_RE.search(line)
        if m:
            try:
                return int(m.group(1))
            except:
                # if parse fails, skip
                continue
    return None

# ----------------------------
# High-level Arduino commands
# ----------------------------
def set_speed(ser, speed_val):
    send_command(ser, f"set speed={int(speed_val)}")
    # optional: wait for ack or status
    time.sleep(0.05)

def set_tau(ser, tau_ms):
    send_command(ser, f"set tau={int(tau_ms)}")
    time.sleep(0.05)

def adc_on(ser):
    send_command(ser, "adc on")
    time.sleep(0.05)

def adc_off(ser):
    send_command(ser, "adc off")
    time.sleep(0.05)

def move_axis(ser, axis, steps):
    """
    axis: 'x' or 'y'
    steps: integer (positive means move in + direction; negative -> - direction)
    Waits for ACK_TEXT after sending command. Updates global xPos/yPos.
    """
    global xPos, yPos
    if steps == 0:
        return True
    if axis not in ('x', 'y'):
        raise ValueError("axis must be 'x' or 'y'")
    if steps > 0:
        cmd = f"{axis}+{int(steps)}"
    else:
        cmd = f"{axis}-{int(abs(steps))}"
    send_command(ser, cmd)
    ok = wait_for_ack(ser, timeout=READ_TIMEOUT)
    if not ok:
        print(f"[warn] No ACK for move {cmd} (timeout).")
        return False
    # update stored positions
    if axis == 'x':
        xPos += steps
    else:
        yPos += steps
    return True

# ----------------------------
# Plotting helpers
# ----------------------------
def create_heatmap(area):
    data = np.full((area, area), np.nan, dtype=float)
    fig, ax = plt.subplots()
    im = ax.imshow(data, origin='lower', interpolation='nearest', aspect='auto')
    ax.set_xlabel("x index")
    ax.set_ylabel("y index")
    ax.set_title("Live scan heatmap")
    cb = fig.colorbar(im, ax=ax)
    plt.ion()
    plt.show()
    return fig, ax, im, data

def update_heatmap(im, data):
    im.set_data(data)
    # autoscale the colormap according to current data (ignoring NaNs)
    try:
        valid = np.isfinite(data)
        if np.any(valid):
            im.set_clim(vmin=np.nanmin(data), vmax=np.nanmax(data))
    except Exception:
        pass
    im.axes.figure.canvas.draw()
    im.axes.figure.canvas.flush_events()

# ----------------------------
# Main scanning routine
# ----------------------------
def run_scan():
    global xPos, yPos, measurement_done

    # Validation
    if Area <= 0:
        print("[error] Area must be > 0")
        return

    # Open serial
    ser = open_serial()

    try:
        # 1) set parameters: speed and tau
        set_speed(ser, speed)
        set_tau(ser, delay_ms)

        # 2) move to desired center (compute relative from current xPos,yPos)
        dx_to_center = center[0] - xPos
        dy_to_center = center[1] - yPos

        print(f"[info] Moving to center: dx={dx_to_center}, dy={dy_to_center}")
        if dx_to_center != 0:
            if not move_axis(ser, 'x', dx_to_center):
                print("[error] Failed to move to center (x). Aborting.")
                return
        if dy_to_center != 0:
            if not move_axis(ser, 'y', dy_to_center):
                print("[error] Failed to move to center (y). Aborting.")
                return

        # 3) compute and move to first scanning point:
        # start at [center[0] + floor(0.5*Area) - 1, center[1] + floor(0.5*Area) + 1]
        half = math.floor(0.5 * Area)
        first_x = center[0] + half - 1
        first_y = center[1] + half + 1
        dx_first = first_x - xPos
        dy_first = first_y - yPos
        print(f"[info] Moving to first scan point ({first_x}, {first_y}) dx={dx_first}, dy={dy_first}")
        if dx_first != 0:
            if not move_axis(ser, 'x', dx_first):
                print("[error] Failed to move to first scanning point (x). Aborting.")
                return
        if dy_first != 0:
            if not move_axis(ser, 'y', dy_first):
                print("[error] Failed to move to first scanning point (y). Aborting.")
                return

        # 4) initialize plot if no measurement before
        if not measurement_done:
            fig, ax, im, data = create_heatmap(Area)
            measurement_done = True
        else:
            # if we had existing plot/data: reuse; but for simplicity create fresh if variable missing
            try:
                im, data
            except NameError:
                fig, ax, im, data = create_heatmap(Area)

        # 5) enable ADC output
        adc_on(ser)

        # 6) scanning loops
        print("[info] Starting scan loops")
        for i in range(Area):
            for j in range(Area):
                # Move x+1
                if not move_axis(ser, 'x', 1):
                    print(f"[error] Move x+1 failed at grid ({j},{i}). Aborting scan.")
                    adc_off(ser)
                    return

                # Wait for ADC value
                adc_val = wait_for_adc_value(ser, timeout=READ_TIMEOUT + (delay_ms / 1000.0) + 0.5)
                if adc_val is None:
                    print(f"[warn] No ADC value received for grid ({j},{i}). Inserting NaN.")
                    value = np.nan
                else:
                    value = adc_val

                # store in data grid
                data[i, j] = value

                # update heatmap
                update_heatmap(im, data)

            # End of row: move x back by Area steps
            if not move_axis(ser, 'x', -Area):
                print(f"[error] Move x-{Area} failed after row {i}. Aborting scan.")
                adc_off(ser)
                return

            # Move y-1 to next row (unless last row)
            if i < Area - 1:
                if not move_axis(ser, 'y', -1):
                    print(f"[error] Move y-1 failed after row {i}. Aborting scan.")
                    adc_off(ser)
                    return


        # 7) disable ADC output
        adc_off(ser)
        print("[info] Scan finished. Returning to center...")

        # 8) move back to center (center[0], center[1])
        dx_back = center[0] - xPos
        dy_back = center[1] - yPos
        if dx_back != 0:
            if not move_axis(ser, 'x', dx_back):
                print("[warn] Failed to move back to center on x.")
        if dy_back != 0:
            if not move_axis(ser, 'y', dy_back):
                print("[warn] Failed to move back to center on y.")

        print("[info] Returned to center. Done.")
        # keep plot open (interactive mode). Prevent program exit closing plot immediately:
        print("[info] Close the plot window to finish.")
        plt.ioff()
        plt.show()

    finally:
        if ser and ser.is_open:
            try:
                ser.close()
            except:
                pass
        print("[serial] Closed.")


if __name__ == "__main__":
    run_scan()
