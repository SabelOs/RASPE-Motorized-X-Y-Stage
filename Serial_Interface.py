import serial
import time
import re

# ===============================
# Serial connection handler class
# ===============================
class SerialConnection:
    def __init__(self, port="COM3", baudrate=115200, timeout=0.2, ack_text="OK"):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ack_text = ack_text
        self.ADC_RE = re.compile(r"ADC:\s*([-+]?\d+)")
        self.ser = None
    
    def set_port(self, port):
        was_open = self.ser and self.ser.is_open
        if was_open:
            self.close()
        self.port = port
        if was_open:
            self.open()
        print(f"[serial] Port set to {self.port}")

    def is_open(self):
        """Return True if the serial connection is open."""
        return self.ser is not None and self.ser.is_open    
    
    def open(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        time.sleep(2.0)  # allow Arduino reset
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        print(f"[serial] Opened {self.port} @ {self.baudrate}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[serial] Closed.")

    def send_command(self, cmd):
        full = f"{cmd}\n"
        self.ser.write(full.encode("utf-8"))
        self.ser.flush()
        print(f">>> {cmd}")

    def read_line(self, timeout=None):
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            s = line.decode("utf-8", errors="replace").strip()
            if s:
                print(f"<<< {s}")
                return s
        return None

    def wait_for_ack(self, timeout=20.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=deadline - time.time())
            if line and self.ack_text in line:
                return True
        return False

    def wait_for_adc_value(self, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=deadline - time.time())
            if not line:
                continue
            match = self.ADC_RE.search(line)
            if match:
                return int(match.group(1))
        return None

    def adc_get_value(self, timeout=2.0):
        """
        Send 'adc read' command to Arduino and return the ADC value.
        Returns None if no valid response is received within timeout.
        """
        self.send_command("adc read")
        value = self.wait_for_adc_value(timeout=timeout)
        if value is not None:
            return value
        else:
            print("[serial] Failed to read ADC value.")
