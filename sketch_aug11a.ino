#include <CNCShield.h>

#define ADC_PIN A5
#define MICROSTEPS_PER_STEP 100

// CNC Shield setup
CNCShield cnc_shield;
StepperMotor *motor_x = cnc_shield.get_motor(0);
StepperMotor *motor_y = cnc_shield.get_motor(1);

// Runtime parameters
unsigned long tau = 200;     // delay after movement in ms
bool adc_enabled = false;    // enable/disable ADC read

// Function declarations
String readCommand();
void executeCommand(String cmd);
void moveMotor(StepperMotor *motor, long steps, bool dir);
void sendLine(String msg);

void setup() {
  Serial.begin(115200);
  cnc_shield.begin();
  cnc_shield.enable();

  motor_x->set_speed(1000);
  motor_y->set_speed(1000);

  sendLine("READY"); // Signal to Python that Arduino is ready
}

void loop() {
  if (Serial.available()) {
    String cmd = readCommand();
    executeCommand(cmd);
  }
}

// Read a full command string from serial
String readCommand() {
  String cmd = Serial.readStringUntil('\n');
  cmd.replace("\r", ""); // Remove carriage return if present
  cmd.trim();
  return cmd;
}

// Execute parsed command
void executeCommand(String cmd) {
  cmd.toLowerCase();

  // ----- Movement Commands -----
  if (cmd.startsWith("x+") || cmd.startsWith("x-") ||
      cmd.startsWith("y+") || cmd.startsWith("y-")) {
    char axis = cmd.charAt(0);
    char sign = cmd.charAt(1);
    long steps = cmd.substring(2).toInt();

    direction_t dir = (sign == '+') ? COUNTER : CLOCKWISE;
    StepperMotor *motor = (axis == 'x') ? motor_x : motor_y;
    
    moveMotor(motor, steps, dir);

    delay(tau); // wait after movement

    sendLine("OK");

    if (adc_enabled) {
      int voltage = analogRead(ADC_PIN);
      sendLine("ADC: " + String(voltage));
    }
    return;
  }

  // ----- Set parameters -----
  if (cmd.startsWith("set tau=")) {
    tau = cmd.substring(8).toInt();
    sendLine("OK");
    return;
  }

  if (cmd.startsWith("adc on")) {
    adc_enabled = true;
    sendLine("OK");
    return;
  }

  if (cmd.startsWith("adc off")) {
    adc_enabled = false;
    sendLine("OK");
    return;
  }

  if (cmd.startsWith("set speed=")) {
    int spd = cmd.substring(10).toInt();
    motor_x->set_speed(spd);
    motor_y->set_speed(spd);
    sendLine("OK");
    return;
  }

  // ----- Manual ADC Read -----
  if (cmd == "adc read") {
    int voltage = analogRead(ADC_PIN);
    sendLine("ADC: " + String(voltage));
    return;
  }

  // ----- Status -----
  if (cmd == "status") {
    sendLine("tau=" + String(tau));
    sendLine("adc=" + String(adc_enabled ? "on" : "off"));
    sendLine("speed=" + String(motor_x->get_speed()));
    return;
  }

  // ----- Help -----
  if (cmd == "help") {
    sendLine("Commands:");
    sendLine("  x+[steps]   - Move X axis CCW");
    sendLine("  x-[steps]   - Move X axis CW");
    sendLine("  y+[steps]   - Move Y axis CCW");
    sendLine("  y-[steps]   - Move Y axis CW");
    sendLine("  set tau=N   - Set delay after move in ms");
    sendLine("  set speed=N - Set motor speed");
    sendLine("  adc on/off  - Enable/disable ADC read after moves");
    sendLine("  adc read    - Read ADC value immediately");
    sendLine("  status      - Show current settings");
    sendLine("  help        - Show this help");
    return;
  }

  // Unknown command
  sendLine("ERR: Unknown command");
}

void moveMotor(StepperMotor *motor, long steps, direction_t dir) {
  motor->set_dir(dir);
  motor->step(steps * MICROSTEPS_PER_STEP);
}

// Always send CRLF for Windows compatibility
void sendLine(String msg) {
  Serial.print(msg);
  Serial.print("\r\n");
}
