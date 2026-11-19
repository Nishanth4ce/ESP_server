"""
=============================================================================
ESP32 IoT Server - Root Launcher
=============================================================================
This script allows you to run `python server.py` directly from the root
workspace directory (ESP_server) or from inside the esp32_iot_server directory.
It automatically sets the working directory to esp32_iot_server and launches
the Flask application.
=============================================================================
"""

import os
import sys

# Determine the path to the esp32_iot_server folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(CURRENT_DIR, "esp32_iot_server")

if os.path.exists(PROJECT_DIR):
    sys.path.insert(0, PROJECT_DIR)
    os.chdir(PROJECT_DIR)

if __name__ == "__main__":
    # Import and run the Flask application
    from server import app
    print("==================================================")
    print("       Starting ESP32 IoT Flask Server")
    print("==================================================")
    print(" * Port: 5000")
    print(" * Host: 0.0.0.0 (Accessible to local Wi-Fi devices)")
    print(" * Web Dashboard: http://localhost:5000")
    print(" * ESP32 API URL: http://<YOUR_LAPTOP_IP>:5000/api/data")
    print("==================================================")
    app.run(host="0.0.0.0", port=5000, debug=True)
