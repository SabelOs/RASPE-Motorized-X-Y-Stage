# Arduino X-Y Stage Scanner

Control software for a **motorized X-Y stage** setup, designed to scan an area and record the signal from an Arduino’s ADC pin. This project enables mapping out a measured signal across a defined region using an **Arduino Uno** equipped with a **CNC Shield V3**.

---

## Features

- Control of a motorized **X-Y stage** via Arduino + CNC Shield V3  
- Supports **4-pin stepper motors** with stepper drivers (A4988 / DRV8825 or similar)  
- Scans a 2D grid and measures an analog signal (ADC pin)  
- Streams measurement data directly over serial for real-time visualization and logging  
- Configurable grid size, step size, and scanning parameters via the UI  

---

## Hardware Requirements

- Arduino Uno  
- CNC Shield V3  
- 2× 4-pin stepper motors 
- Motorized X-Y stage (custom or commercial)  
- Signal source connected to Arduino’s analog input (e.g., A0)  

---

## Software Requirements

- Arduino IDE (or PlatformIO) for uploading firmware  
- Python for the control and visualization software  
- Dependencies are handled through the provided **UI**, no command-line usage required  

---

## Usage

1. **Upload the firmware** to the Arduino Uno (`sketch_aug11a.ino`).  
2. **Start the Python software** and connect to the Arduino via the UI.  
3. **Configure scan parameters** (grid size, step size, ADC channel) in the UI.  
4. **Run the scan** – the X-Y stage moves step-by-step, while ADC values are collected and streamed.  
5. **Visualize results** directly in the UI (2D maps and plots).  

---

## Example Output

![Example Heatmap](docs/example_heatmap.png)  
<img width="641" height="518" alt="test-scan-ariy-ring" src="https://github.com/user-attachments/assets/2c3ab573-47e4-4f91-a8dd-d930a072995d" />


---

## License

This project is released under the MIT License.  
