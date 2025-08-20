import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import serial.tools.list_ports
import sys

from Scan import Scanner
from Serial_Interface import SerialConnection  


# ===============================
#            Main App
# ===============================
class ScanApp(tk.Tk):
    
    def __init__(self, baudrate=115200, workspace_size=200):
        super().__init__()
        self.title("Arduino Scanner")
        self.geometry("1000x600")

        self.serial_conn = SerialConnection(port="COM3", baudrate=baudrate)
        self.scanner = None
        self.workspace_size = workspace_size
        self.data = np.full((workspace_size, workspace_size), np.nan, dtype=float)

        # Store plot elements for overlay
        self.scan_rect = None
        self.center_marker = None

        self._create_widgets()

        #Now create the scanner object:
        self._create_scanner()
        
        # Ensure clean exit when window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    
    
    
    
    
    
    def _create_widgets(self):
        # Left control panel
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)

                # --- Serial Control ---
        serial_label = ttk.Label(control_frame, text="--- Serial Control ---", font=("TkDefaultFont", 10, "bold"))
        serial_label.grid(row=0, column=0, columnspan=3, pady=(5, 2), sticky="w")

        ttk.Label(control_frame, text="Serial Port:").grid(row=1, column=0, sticky="w")
        self.port_combo = ttk.Combobox(control_frame, width=15, state="readonly")
        self.port_combo.grid(row=1, column=1, padx=5)
        self._refresh_ports()

        refresh_btn = ttk.Button(control_frame, text="Refresh", command=self._refresh_ports)
        refresh_btn.grid(row=1, column=2, padx=5)

        self.connect_btn = ttk.Button(control_frame, text="Connect", command=self._connect_serial)
        self.connect_btn.grid(row=2, column=0, columnspan=2, pady=5)

        if self.serial_conn.is_open:
            self.conn_status = tk.StringVar(value="Not connected")
        else:
            self.conn_status = tk.StringVar(value="Not connected")
        ttk.Label(control_frame, textvariable=self.conn_status, foreground="red").grid(row=2, column=2, padx=5)

        # --- Scan Control ---
        scan_label = ttk.Label(control_frame, text="--- Scan Control ---", font=("TkDefaultFont", 10, "bold"))
        scan_label.grid(row=3, column=0, columnspan=3, pady=(10, 2), sticky="w")

        ttk.Label(control_frame, text="Extension:").grid(row=4, column=0, sticky="w")
        self.ext_entry = ttk.Entry(control_frame, width=10)
        self.ext_entry.insert(0, "3")  # example: 3 -> 7x7 grid
        self.ext_entry.grid(row=4, column=1)
        self.ext_entry.bind("<KeyRelease>", self.on_center_change)

        ttk.Label(control_frame, text="Center X:").grid(row=5, column=0, sticky="w")
        self.center_x_entry = ttk.Entry(control_frame, width=10)
        self.center_x_entry.insert(0, "100")
        self.center_x_entry.grid(row=5, column=1)
        self.center_x_entry.bind("<KeyRelease>", self.on_center_change)

        ttk.Label(control_frame, text="Center Y:").grid(row=6, column=0, sticky="w")
        self.center_y_entry = ttk.Entry(control_frame, width=10)
        self.center_y_entry.insert(0, "100")
        self.center_y_entry.grid(row=6, column=1)
        self.center_y_entry.bind("<KeyRelease>", self.on_center_change)

        ttk.Label(control_frame, text="Stepsize:").grid(row=7, column=0, sticky="w")
        self.stepsize_entry = ttk.Entry(control_frame, width=10)
        self.stepsize_entry.insert(0, "1")
        self.stepsize_entry.grid(row=7, column=1)

        ttk.Label(control_frame, text="Delay (ms):").grid(row=8, column=0, sticky="w")
        self.delay_entry = ttk.Entry(control_frame, width=10)
        self.delay_entry.insert(0, "100")
        self.delay_entry.grid(row=8, column=1)

        self.start_button = ttk.Button(control_frame, text="Start Scan", command=self.start_scan)
        self.start_button.grid(row=9, column=0)

        self.abort_button = ttk.Button(control_frame, text="Abort", command=self.abort_scan)
        self.abort_button.grid(row=9, column=1)

        # --- Manual Control ---
        manual_label = ttk.Label(control_frame, text="--- Manual Control ---", font=("TkDefaultFont", 10, "bold"))
        manual_label.grid(row=10, column=0, columnspan=3, pady=(10, 2), sticky="w")

        # Shared stepsize variable
        self.stepsize_var = tk.StringVar(value="1")

        # Bind the scan control stepsize entry to the shared var
        self.stepsize_entry.config(textvariable=self.stepsize_var)

        # Manual stepsize entry (shares the same var)
        ttk.Label(control_frame, text="Stepsize:").grid(row=11, column=0, sticky="w")
        self.manual_stepsize_entry = ttk.Entry(control_frame, width=10, textvariable=self.stepsize_var)
        self.manual_stepsize_entry.grid(row=11, column=1)

        # Row index for manual buttons (n = 12 now)
        n = 12

        self.up_btn = ttk.Button(control_frame, text="UP",
                                 command=lambda: self.scanner_move("y", +1))
        self.up_btn.grid(row=n, column=1, pady=2)

        self.left_btn = ttk.Button(control_frame, text="LEFT",
                                   command=lambda: self.scanner_move("x", -1))
        self.left_btn.grid(row=n+1, column=0, pady=2)

        self.right_btn = ttk.Button(control_frame, text="RIGHT",
                                    command=lambda: self.scanner_move("x", +1))
        self.right_btn.grid(row=n+1, column=2, pady=2)

        self.down_btn = ttk.Button(control_frame, text="DOWN",
                                   command=lambda: self.scanner_move("y", -1))
        self.down_btn.grid(row=n+2, column=1, pady=2)


        # Right plot panel
        plot_frame = ttk.Frame(self)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig, self.ax = plt.subplots()

        # Heatmap with shifted extent so pixel centers are at integer coords
        nx, ny = self.data.shape
        self.im = self.ax.imshow(
            self.data,
            origin="lower",
            interpolation="nearest",
            aspect="auto",
            extent=[-0.5, nx - 0.5, -0.5, ny - 0.5]   # <- important change
        )

        self.ax.set_xlabel("X Steps")
        self.ax.set_ylabel("Y Steps")
        self.ax.grid()
        self.fig.colorbar(self.im, ax=self.ax)

        # Set fixed view initially (still works with shifted extent)
        self.ax.set_xlim(80, 120)
        self.ax.set_ylim(80, 120)

        # Add to Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add interactive toolbar (zoom, pan, save, etc.)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        self.toolbar.update()

        #Lastly, draw the rectangle and center cross
        self.on_center_change()


    def _create_scanner(self):
        try:
            extension = int(self.ext_entry.get())
            center_x = int(self.center_x_entry.get())
            center_y = int(self.center_y_entry.get())
            delay_ms = int(self.delay_entry.get())
            stepsize = int(self.stepsize_entry.get())
        except ValueError:
            print("[error] Invalid input")
            return

        self.draw_overlay((center_x, center_y), extension)

        self.scanner = Scanner(
            serial_conn=self.serial_conn,
            extension=extension,
            center=(center_x, center_y),
            speed=1000,
            delay_ms=delay_ms,
            data_array=self.data,
            im=self.im,
            stepsize=stepsize,
            xpos= center_x,
            ypos= center_y
        )

    def _refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combo["values"] = port_list
        if port_list:
            self.port_combo.current(0)

    def _connect_serial(self):
        port = self.port_combo.get()
        if not port:
            self.conn_status.set("No port selected")
            return
        try:
            self.serial_conn.set_port(port)
            self.serial_conn.open()
            self.conn_status.set(f"Connected to {port}")
            self.conn_status_label_color("green")
        except Exception as e:
            self.conn_status.set(f"Error: {e}")
            self.conn_status_label_color("red")

    def conn_status_label_color(self, color):
        label = self.conn_status_label_widget()
        if label:
            label.config(foreground=color)

    def conn_status_label_widget(self):
        # Find the label widget with textvariable = self.conn_status
        for child in self.children.values():
            for subchild in child.winfo_children():
                if isinstance(subchild, ttk.Label) and getattr(subchild, "cget", lambda x: None)("textvariable") == str(self.conn_status):
                    return subchild
        return None

    def draw_overlay(self, center, extension):
        if self.scan_rect:
            self.scan_rect.remove()
        if self.center_marker:
            self.center_marker.remove()

        length = 2 * extension + 1  # full span
        lower_left_x = center[0] - extension 
        lower_left_y = center[1] - extension 

        self.scan_rect = Rectangle(
            (lower_left_x-0.5, lower_left_y-0.5), #the -0.5 is to adjust for the shift in axis and to have the center of the pixels be the position
            length, length,
            fill=False, linestyle="--", edgecolor="black", linewidth=1.5
        )
        self.ax.add_patch(self.scan_rect)

        self.center_marker = self.ax.plot(center[0], center[1], marker="x", color="red", markersize=5, mew=2)[0]
        self.canvas.draw_idle()



    def start_scan(self):
        if not self.serial_conn.is_open():
            print("[error] Serial not connected")
            return

        if self.scanner.abort:
            self.scanner.abort = False

        self.scanner.run_scan()

    
    def abort_scan(self):
        self.scanner.abort=True

    
    def on_center_change(self, event=None): #this is redundant code, that just updates the black box and center spot as well as the scanner object
        try:
            extension = int(self.ext_entry.get())
            center_x = int(self.center_x_entry.get())
            center_y = int(self.center_y_entry.get())
        except ValueError:
            return

        self.draw_overlay((center_x, center_y), extension)
        
        if self.scanner != None:
            #update scanner
            self.scanner.center[0]= center_x
            self.scanner.center[1]= center_y
            self.scanner.extension= extension



    def scanner_move(self, axis, direction):
        try:
            step = int(self.stepsize_entry.get())
        except ValueError:
            step = 1  # fallback if entry is empty/invalid

        # direction is expected to be ±1
        self.scanner.move_axis(axis, direction * step)
        self.serial_conn.wait_for_ack()
    
    def on_closing(self):
        if self.serial_conn.is_open():
            self.serial_conn.close()
        self.destroy()
        sys.exit(0)  # force Python to exit

if __name__ == "__main__":
    app = ScanApp()
    app.mainloop()
