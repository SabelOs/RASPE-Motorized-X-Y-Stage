import time
import numpy as np
import math

# ===============================
#           Scan Logic
# ===============================
class Scanner:
    def __init__(self, serial_conn, extension, center, speed, delay_ms, data_array, im, stepsize, xpos, ypos):
        self.serial = serial_conn
        self.extension = int(extension)
        self.area = self.extension * 2 + 1
        self.center = [int(center[0]), int(center[1])]
        self.speed = int(speed)
        self.delay_ms = int(delay_ms)
        self.xPos = xpos
        self.yPos = ypos
        self.stepsize = stepsize
        self.data = data_array
        self.im = im
        self.abort = False
        # create the dot once, with initial position
        (self.dot,) = self.im.axes.plot(self.xPos, self.yPos, "go", markersize=5)

    def update_heatmap(self):
        valid = np.isfinite(self.data)
        if np.any(valid):
            self.im.set_clim(vmin=np.nanmin(self.data), vmax=np.nanmax(self.data))
        self.im.set_data(self.data)

        # update dot position
        self.dot.set_data([self.xPos], [self.yPos])

        self.im.axes.figure.canvas.draw_idle()
        self.im.axes.figure.canvas.flush_events()

    
    def run_scan(self):
        print("STEPSIZE:", self.stepsize)
        if self.extension <= 0:
            print("[error] Area must be > 0")
            return

        # Only proceed if connection is open
        if not self.serial.is_open():
            print("[error] Serial connection is not open.")
            return

        self.serial.send_command(f"set speed={self.speed}")
        if not self.serial.wait_for_ack():
            return
        
        self.serial.send_command(f"set tau={self.delay_ms}")
        if not self.serial.wait_for_ack():
            return
        
        # Move to center
        dx = self.center[0] - self.xPos
        dy = self.center[1] - self.yPos 
        if not self.move_axis('x', dx):
            return
        if not self.move_axis('y', dy):
            return

        # Move to first scan point
        if not self.move_axis('x', -self.extension): #move to first scan point x pos
            return
        if not self.move_axis('y', -self.extension):
            return
        
        self.serial.send_command("adc on") #turn on adc now to get 
        #Wait for OK
        if not self.serial.wait_for_ack():
            return
        
        #print("Current Position:", self.xPos, self.yPos)

        for i in range(math.floor(((2*self.extension)/self.stepsize))+1):
            for j in range(math.floor(((2*self.extension)/self.stepsize))+1):
                if self.abort:
                    return
                #print("Current Position:", self.xPos, self.yPos)
                
                # measure ADC Value
                val = self.serial.adc_get_value()

                if val is not None:
                    half_step = math.floor(self.stepsize / 2)

                    for yy in range(self.yPos - half_step, self.yPos + half_step + 1):
                        for xx in range(self.xPos - half_step, self.xPos + half_step + 1):
                            if (0 <= yy < self.data.shape[0]) and (0 <= xx < self.data.shape[1]):
                                self.data[yy, xx] = val
                else:
                    if (0 <= self.yPos < self.data.shape[0]) and (0 <= self.xPos < self.data.shape[1]):
                        self.data[self.yPos, self.xPos] = np.nan
                
                #Do x-step
                if not self.move_axis('x', self.stepsize):
                    return
                
                
            #go back x-row
            if not self.move_axis('x', -self.stepsize* (j+1)):
                return
            
            #do y-step
            if i < math.floor(((2*self.extension)/self.stepsize))+1:
                if not self.move_axis('y', self.stepsize):
                    return

        self.serial.send_command("adc off")

        # Return to center
        self.move_axis('x', self.center[0] - self.xPos)
        self.move_axis('y', self.center[1] - self.yPos)
        #print("Current Position:", self.xPos, self.yPos)



    def move_axis(self, axis, steps):
        """
        Move a given axis ('x' or 'y') by a number of steps.
        Format actually expected by Arduino: x+10 or y-2
        """
        if axis not in ('x', 'y'):
            print(f"[error] Invalid axis: {axis}")
            return False

        if steps == 0:
            return True  # No movement needed

        sign = "+" if steps > 0 else "-"
        cmd = f"{axis}{sign}{abs(steps)}"   # e.g. "x+10" or "y-2"

        self.serial.send_command(cmd)
        if not self.serial.wait_for_ack(timeout=5.0):
            print(f"[error] No ACK for {cmd}")
            return False
        
        # Update internal tracking
        if axis == 'x':
            self.xPos += steps
        else:
            self.yPos += steps
        #update the positions in the plot
        self.update_heatmap()

        return True

