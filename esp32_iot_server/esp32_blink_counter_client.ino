/* ==============================================================================
   ESP32-C3 Optical Pulse Counter + Energy Telemetry
   ==============================================================================
   Hardware:
     - Board:       ESP32-C3 (select "ESP32C3 Dev Module" in Arduino IDE Tools > Board)
     - Sensor:      BPX43 phototransistor on GPIO pin 3
     - Circuit:     Light detected = LOW (raw=0), No light = HIGH (raw=1)
                    So: sensor = !raw  (1 when light is detected)

   How it works:
     - Counts LED blinks from the optical pulse output of the energy meter
     - Every rising edge (no light → light) = 1 pulse = 0.001 kWh
     - Sends blink count + kWh to your Flask server via HTTPS POST every 5 seconds
     - HTTPS is required because the ngrok tunnel URL uses SSL (https://)

   Arduino IDE Settings (Tools menu):
     - Board:           ESP32C3 Dev Module
     - USB CDC On Boot: Enabled   ← IMPORTANT for Serial to work on ESP32-C3
     - Upload Speed:    921600
     - Port:            Your COM port (e.g. COM3, COM6)
   ============================================================================== */

#include <WiFi.h>
#include <WiFiClientSecure.h>   // Required for HTTPS (ngrok uses https://)
#include <HTTPClient.h>

// ============================================================================
// 1. CONFIGURATION - Edit these values
// ============================================================================

// Sensor pin (BPX43 phototransistor)
#define SENSOR_PIN 3

// Energy meter pulse constant: 3200 blinks = 1 kWh
const float KWH_PER_PULSE = 1.0 / 3200.0; // 0.0003125 kWh per pulse

// House identifier
const char* HOUSE_ID = "IN1";
const char* TRANSFORMER_ID = "TC1";

// Wi-Fi credentials (friend's hotspot or Wi-Fi)
const char* ssid     = "OnePlus 11R 5G";
const char* password = "192837465";

// ngrok Forwarding URL + /api/data
// Use the FORWARDING URL from ngrok screen (not the Web Interface URL)
// Example: https://overflow-marbles-surround.ngrok-free.dev/api/data
const char* serverUrl = "https://overflow-marbles-surround.ngrok-free.dev/api/data";

// How often to send data to server (milliseconds)
const unsigned long SEND_INTERVAL = 5000; // 5 seconds

// ============================================================================
// 2. GLOBAL VARIABLES
// ============================================================================

unsigned long blinkCount = 0;  // Total blink count since power on or reset
int lastSensor = 0;            // Previous sensor state (for edge detection)
unsigned long lastSendTime = 0; // Timestamp of last HTTP POST

// ============================================================================
// 3. SETUP
// ============================================================================

void setup() {
  // Start serial communication at 115200 baud
  // In Arduino IDE: Tools > Serial Monitor > set to 115200
  Serial.begin(115200);
  delay(1500); // Wait for Serial to initialise on ESP32-C3

  Serial.println("\n==============================================");
  Serial.println("  ESP32-C3 Pulse Counter + Telemetry Client");
  Serial.println("==============================================");
  Serial.println("Commands: Send 't' or 'T' in Serial Monitor to reset count.");

  // Set up sensor pin
  pinMode(SENSOR_PIN, INPUT);

  // Read the initial sensor state so we don't count a false first blink
  int raw = digitalRead(SENSOR_PIN);
  lastSensor = !raw;
  Serial.print("Sensor Pin GPIO");
  Serial.print(SENSOR_PIN);
  Serial.print(" initial state: ");
  Serial.println(lastSensor ? "LIGHT" : "DARK");

  // Connect to Wi-Fi
  Serial.print("\nConnecting to Wi-Fi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  WiFi.setTxPower(WIFI_POWER_8_5dBm); // Reduce power for stability on C3

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Signal Strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n[WiFi] WARNING: Could not connect! Will keep retrying in loop.");
  }

  Serial.println("\n[Ready] Counting pulses...");
  Serial.println("----------------------------------------------");
}

// ============================================================================
// 4. MAIN LOOP
// ============================================================================

void loop() {

  // --------------------------------------------------------------------------
  // A. Handle Serial commands (reset count with 't' or 'T')
  // --------------------------------------------------------------------------
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 't' || cmd == 'T') {
      blinkCount = 0;
      Serial.println("\n>>> Count Reset to 0! <<<\n");
    }
  }

  // --------------------------------------------------------------------------
  // B. Read BPX43 sensor and detect rising edge (pulse)
  // --------------------------------------------------------------------------
  int raw = digitalRead(SENSOR_PIN);

  // Invert: Light detected = LOW (raw=0), so sensor=1 when light is on
  int sensor = !raw;

  // Detect rising edge: DARK (0) → LIGHT (1) = one pulse/blink
  if (lastSensor == 0 && sensor == 1) {
    blinkCount++;
    float currentKwh = blinkCount * KWH_PER_PULSE;

    Serial.print("[BLINK] Count = ");
    Serial.print(blinkCount);
    Serial.print("  |  Energy = ");
    Serial.print(currentKwh, 3);
    Serial.println(" kWh");
  }

  lastSensor = sensor;

  // --------------------------------------------------------------------------
  // C. Send data to Flask server every SEND_INTERVAL milliseconds (non-blocking)
  // --------------------------------------------------------------------------
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = now;

    if (WiFi.status() == WL_CONNECTED) {
      sendTelemetry();
    } else {
      Serial.println("[WiFi] Disconnected. Reconnecting...");
      WiFi.reconnect();
    }
  }

  // Short delay for debouncing the optical sensor (2ms = 500Hz sample rate)
  delay(2);
}

// ============================================================================
// 5. SEND TELEMETRY FUNCTION
// ============================================================================

void sendTelemetry() {
  float load_kwh = blinkCount * KWH_PER_PULSE;

  // Build the JSON payload string
  String jsonPayload = "{";
  jsonPayload += "\"house_id\":\"" + String(HOUSE_ID) + "\",";
  jsonPayload += "\"blink_count\":" + String(blinkCount) + ",";
  jsonPayload += "\"load_kwh\":" + String(load_kwh, 3) + ",";
  jsonPayload += "\"transformer_id\":\"" + String(TRANSFORMER_ID) + "\"";
  jsonPayload += "}";

  Serial.println("\n[HTTP] Sending to server...");
  Serial.print("[HTTP] Payload: ");
  Serial.println(jsonPayload);

  // Use WiFiClientSecure for HTTPS (ngrok URL starts with https://)
  WiFiClientSecure client;

  // Skip SSL certificate verification (safe for development/local tunnel)
  // This is needed because ngrok uses a dynamic certificate
  client.setInsecure();

  HTTPClient http;

  // Begin HTTPS connection
  if (!http.begin(client, serverUrl)) {
    Serial.println("[HTTP] Failed to begin connection!");
    return;
  }

  // Set headers
  http.addHeader("Content-Type", "application/json");
  http.addHeader("ngrok-skip-browser-warning", "true"); // Bypass ngrok browser page

  // Send POST request
  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.print("[HTTP] Response Code: ");
    Serial.println(httpCode);
    Serial.print("[HTTP] Server Reply: ");
    Serial.println(response);
  } else {
    Serial.print("[HTTP] Error Code: ");
    Serial.print(httpCode);
    Serial.print(" | Error: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
  Serial.println("----------------------------------------------");
}
