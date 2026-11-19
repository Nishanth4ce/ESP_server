# Transformer Energy Monitoring System (with Tunneling)

A complete IoT energy monitoring system built with **Python (Flask)** and **vanilla HTML/CSS/JavaScript**.

This project connects an **ESP32 optical pulse blink counter** (running at your friend's house on a different Wi-Fi network) to your **laptop Flask server** (running at your home) using **secure HTTP tunneling**.

---

## 📁 Project Structure

```text
esp32_iot_server/
│
├── server.py                        # Flask backend & telemetry API (in kWh)
├── requirements.txt                 # Dependencies (Flask >= 3.0.0)
├── README.md                        # Master setup guide & tunneling tutorial
├── esp32_blink_counter_client.ino   # Ready-to-flash Arduino C++ pulse counter
│
├── templates/
│   └── index.html                   # Two-block dark dashboard layout (kWh)
│
└── static/
    ├── style.css                    # Energy monitoring styling & pulse animation
    └── script.js                    # Auto-refreshing fetch client (every 2s)
```

---

## 🌐 The Tunneling Concept Explained

### The Problem: Why Direct Local IP Fails
- Your laptop is at your house connected to your Wi-Fi router. Your router assigns it a private local IP (e.g., `192.168.1.10`).
- Your ESP32 is at your friend's house connected to their Wi-Fi router. Their router assigns it an internal IP (e.g., `192.168.0.45`).
- **Private local IPs cannot communicate directly across different Wi-Fi networks** because home routers have firewalls and NAT (Network Address Translation). An ESP32 at your friend's house cannot reach `192.168.1.10`.

### The Solution: A Secure Tunnel
```
┌─────────────────────────┐               Internet               ┌───────────────────────────────┐
│ ESP32 @ Friend's Wi-Fi  │ ───────────────────────────────────> │  Secure Public Tunnel         │
│ (Optical Pulse Counter) │   POST https://xyz.ngrok.app/api/data│  (e.g., ngrok / pinggy)       │
└─────────────────────────┘                                      └──────────────┬────────────────┘
                                                                                │
                                                                                │ Forwards securely
                                                                                ▼
                                                                 ┌───────────────────────────────┐
                                                                 │  Your Laptop @ Your Home      │
                                                                 │  Flask Server (localhost:5000)│
                                                                 └───────────────────────────────┘
```

A **tunneling service** creates a secure, public HTTPS bridge on the Internet that forwards incoming HTTP requests directly into your laptop's `localhost:5000`.

---

## 🚀 Step-by-Step Setup Guide

### Step 1: Start the Flask Server on Your Laptop

Open your terminal in VS Code:
```powershell
cd C:\Users\LENOVO\Documents\ESP_server\esp32_iot_server
.\venv\Scripts\python.exe server.py
```

Open your browser to: **[http://localhost:5000](http://localhost:5000)**  
You will see:
- **Block 1 (House Energy Details)**: `IN1 [ESP32 (WAITING)]`, plus simulated houses `IN2`, `IN3`, `IN4`.
- **Block 2 (Transformer Details)**: Total Input `30.0 kWh`, Total Consumed, Capacity `30.0 kWh`, and the consumption vs input progress bar.

---

### Step 2: Start the Tunnel to Get a Public HTTPS URL

Choose either **Method A (Pinggy - No installation needed)** or **Method B (ngrok - Recommended)**:

#### Method A: Pinggy (Zero-Install — Instant)
Open a **new separate terminal** on your laptop and run:
```powershell
ssh -p 443 -R0:localhost:5000 a.pinggy.io
```
Pinggy will instantly display a public HTTPS URL, for example:
```text
https://tunnellink-xxxx.a.pinggy.link
```

---

#### Method B: ngrok (Most Reliable & Popular)
1. Download ngrok from [ngrok.com/download](https://ngrok.com/download) or install via PowerShell:
   ```powershell
   winget install ngrok
   ```
2. Sign up for a free account at [dashboard.ngrok.com](https://dashboard.ngrok.com) and copy your AuthToken.
3. Paste your token in PowerShell:
   ```powershell
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```
4. Start forwarding port 5000:
   ```powershell
   ngrok http 5000
   ```
5. ngrok will show your public HTTPS address:
   ```text
   Forwarding   https://abc123xyz.ngrok-free.app -> http://localhost:5000
   ```

---

### Step 3: Configure the ESP32 Code

Open [`esp32_blink_counter_client.ino`](./esp32_blink_counter_client.ino) in Arduino IDE:

1. **Enter your friend's Wi-Fi details**:
   ```cpp
   const char* ssid = "FRIENDS_WIFI_NAME";
   const char* password = "FRIENDS_WIFI_PASSWORD";
   ```

2. **Paste your Tunnel URL**:
   Combine your tunnel URL with `/api/data`:
   ```cpp
   const char* serverUrl = "https://abc123xyz.ngrok-free.app/api/data";
   ```

3. Connect the BPX43 phototransistor to **Pin 3** (or your chosen pin):
   - Circuit: Light detected = LOW (sensor = `!raw`).

4. Upload the code to your ESP32.

---

### Step 4: Verify the Complete Flow

1. Power on the ESP32 at your friend's house.
2. The ESP32 connects to your friend's Wi-Fi.
3. When an LED blinks in front of the BPX43 sensor:
   - The ESP32 detects the pulse: `[BLINK] Count = 1 | Energy = 0.001 kWh`.
   - Every 5 seconds, it sends an HTTP POST request to the tunnel.
4. The tunnel forwards the request to your laptop.
5. In your Flask terminal, you will see:
   ```text
   [21:15:00] ESP32 Live Packet -> House: IN1 | Blinks: 1 | Energy: 0.001 kWh | Total Consumed: 21.101 / 30.0 kWh
   ```
6. On your dashboard at **[http://localhost:5000](http://localhost:5000)**:
   - `IN1` transitions to **`LIVE ESP32`** with a green pulse dot.
   - Shows the live blink count and energy in **kWh**.
   - The bottom running total adds `IN1` to the other simulated houses (`IN2`, `IN3`, `IN4`).
   - The Transformer overview compares **Total Consumed vs 30.0 kWh Total Input** with a real-time progress bar!

---

## ⚡ Quick Test Without Hardware

You can also test the tunnel right from your command line:

```powershell
Invoke-RestMethod -Uri "https://YOUR_TUNNEL_URL/api/data" -Method POST -ContentType "application/json" -Body '{"house_id": "IN1", "blink_count": 50, "load_kwh": 0.05, "transformer_id": "TC1"}'
```

The dashboard will immediately reflect 50 blinks and 0.05 kWh for `IN1`!
