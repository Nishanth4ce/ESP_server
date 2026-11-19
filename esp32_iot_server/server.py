"""
=============================================================================
ESP32 IoT Server - Transformer Load & Energy Monitoring Backend (Flask)
=============================================================================
Monitors electrical energy consumption (in kWh) across multiple houses (IN1..INn)
connected to a distribution transformer (TC1).

Features:
  - Energy Units: All values measured in kWh (kilowatt-hours).
  - ESP32 Live Node (IN1): Receives real-time optical pulse blink counts from
    the ESP32 (phototransistor sensor on pin 3) and converts them to kWh.
  - Multi-House Simulation: Generates realistic background load for other houses
    (IN2, IN3, IN4) under the same transformer.
  - Transformer Telemetry:
      * Transformer Total Input: 30.0 kWh (Distribution Transformer input)
      * Total Consumed: Sum of all house loads (IN1 + IN2 + IN3 + IN4)
      * Utilization & Efficiency tracking (Consumed vs Input 30.0 kWh)
  - Tunneling Ready: Fully compatible with ngrok, localtunnel, Cloudflare,
    or pinggy so an ESP32 on a friend's Wi-Fi can send data to this laptop.
=============================================================================
"""

import random
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# Initialize Flask
app = Flask(__name__)

# -----------------------------------------------------------------------------
# TRANSFORMER BASELINE PARAMETERS
# -----------------------------------------------------------------------------
# Transformer rated input energy baseline: 30.0 kWh
TRANSFORMER_INPUT_KWH = 30.0

transformer_data = {
    "transformer_id": "TC1",
    "tc_count": 1,
    "total_input_kwh": TRANSFORMER_INPUT_KWH,
    "total_consumed_kwh": 0.0,
    "capacity_kwh": TRANSFORMER_INPUT_KWH,
    "last_updated": None,
    "status": "ONLINE"
}

# Energy meter calibration constant: 3200 blinks (pulses) = 1 kWh
PULSES_PER_KWH = 3200

# -----------------------------------------------------------------------------
# IN-MEMORY HOUSE DATA
# -----------------------------------------------------------------------------
# IN1 is reserved for the live physical ESP32 node.
# IN2, IN3, IN4 have simulated realistic energy consumption (calibrated to 3200 imp/kWh).
houses_data = {
    "IN1": {
        "load_kwh": 0.0,
        "blink_count": 0,
        "raw_blink_count": 0,
        "blink_offset": 0,
        "start_time": None,
        "is_live": True,
        "last_updated": "Waiting for ESP32...",
        "status": "WAITING"
    },
    "IN2": {
        "load_kwh": 6.8,
        "blink_count": int(6.8 * PULSES_PER_KWH),  # 21,760 blinks
        "raw_blink_count": int(6.8 * PULSES_PER_KWH),
        "blink_offset": 0,
        "start_time": "16:00:00",
        "is_live": False,
        "last_updated": "Active (Simulated)",
        "status": "ONLINE"
    },
    "IN3": {
        "load_kwh": 8.4,
        "blink_count": int(8.4 * PULSES_PER_KWH),  # 26,880 blinks
        "raw_blink_count": int(8.4 * PULSES_PER_KWH),
        "blink_offset": 0,
        "start_time": "16:00:00",
        "is_live": False,
        "last_updated": "Active (Simulated)",
        "status": "ONLINE"
    },
    "IN4": {
        "load_kwh": 5.9,
        "blink_count": int(5.9 * PULSES_PER_KWH),  # 18,880 blinks
        "raw_blink_count": int(5.9 * PULSES_PER_KWH),
        "blink_offset": 0,
        "start_time": "16:00:00",
        "is_live": False,
        "last_updated": "Active (Simulated)",
        "status": "ONLINE"
    }
}


def recalculate_transformer_totals():
    """
    Recalculates the total energy consumed across all houses (sum of kWh)
    and updates the transformer consumption metrics.
    """
    global houses_data, transformer_data
    total_consumed = round(sum(h["load_kwh"] for h in houses_data.values()), 3)
    transformer_data["total_consumed_kwh"] = total_consumed
    return total_consumed


# Initial calculation for default values
recalculate_transformer_totals()


@app.route("/")
def index():
    """
    Route: / (GET)
    Renders the web dashboard HTML template (templates/index.html).
    """
    return render_template("index.html")


@app.route("/api/data", methods=["GET", "POST"])
def api_data():
    """
    Route: /api/data
    GET  -> Returns full dashboard telemetry (all houses in kWh + transformer summary).
    POST -> Receives sensor payload from the ESP32 (pulse blink count / kWh).
    """
    global houses_data, transformer_data

    # -------------------------------------------------------------------------
    # 1. ESP32 SENDING DATA (HTTP POST)
    # -------------------------------------------------------------------------
    if request.method == "POST":
        # Check Content-Type
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Invalid format: Request body must be JSON (Content-Type: application/json)"
            }), 400

        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({
                "status": "error",
                "message": "Malformed JSON: Could not parse JSON data."
            }), 400

        # Extract house ID (defaults to "IN1" if unspecified)
        raw_house_id = payload.get("house_id") or payload.get("device_id") or "IN1"
        house_id = str(raw_house_id).strip().upper()

        current_time = datetime.now().strftime("%H:%M:%S")

        # Existing house state
        existing = houses_data.get(house_id, {})
        blink_offset = existing.get("blink_offset", 0)
        start_time = existing.get("start_time")
        if not start_time:
            start_time = current_time

        # Extract raw optical blink count
        raw_blinks = payload.get("blink_count")
        raw_blink_count = 0
        if raw_blinks is not None:
            try:
                raw_blink_count = int(raw_blinks)
            except (ValueError, TypeError):
                raw_blink_count = 0

        # If hardware reset occurred on ESP32 (e.g. Serial 't' command), reset offset
        if raw_blink_count < blink_offset:
            blink_offset = 0

        effective_blinks = max(0, raw_blink_count - blink_offset)

        # Extract energy in kWh (calibrated: 1 kWh = 3200 blinks)
        raw_load = payload.get("load_kwh")
        if raw_load is None:
            raw_load = payload.get("load_kva")

        # Calculate exact kWh from effective blinks (3200 blinks = 1 kWh)
        if raw_blinks is not None:
            load_kwh = round(effective_blinks / PULSES_PER_KWH, 3)
            blink_count = effective_blinks
        elif raw_load is not None:
            try:
                load_kwh = round(float(raw_load), 3)
                blink_count = int(load_kwh * PULSES_PER_KWH)
                raw_blink_count = blink_count
            except (ValueError, TypeError):
                return jsonify({
                    "status": "error",
                    "message": "Field 'load_kwh' must be a valid number (e.g. 3.2)."
                }), 400
        else:
            return jsonify({
                "status": "error",
                "message": "Missing required field: 'load_kwh' or 'blink_count'"
            }), 400

        # Update the reporting house (IN1 is the live ESP32 node)
        houses_data[house_id] = {
            "load_kwh": load_kwh,
            "blink_count": blink_count,
            "raw_blink_count": raw_blink_count,
            "blink_offset": blink_offset,
            "start_time": start_time,
            "is_live": True if house_id == "IN1" else False,
            "last_updated": current_time,
            "status": "ONLINE"
        }

        # Optional: update transformer input if supplied by caller, otherwise keep 30.0 kWh
        if payload.get("total_input_kwh") is not None:
            try:
                transformer_data["total_input_kwh"] = round(float(payload.get("total_input_kwh")), 1)
                transformer_data["capacity_kwh"] = transformer_data["total_input_kwh"]
            except (ValueError, TypeError):
                pass

        if payload.get("transformer_id"):
            transformer_data["transformer_id"] = str(payload.get("transformer_id")).strip()

        # Recalculate running total across all houses
        total_consumed = recalculate_transformer_totals()
        transformer_data["last_updated"] = current_time
        transformer_data["status"] = "ONLINE"

        print(f"[{current_time}] ESP32 Live Packet -> House: {house_id} | Blinks: {blink_count} (Raw: {raw_blink_count}) | Started: {start_time} | Energy: {load_kwh} kWh | Total Consumed: {total_consumed} / {transformer_data['total_input_kwh']} kWh")

        return jsonify({
            "status": "success",
            "message": "Data received successfully",
            "house_id": house_id,
            "load_kwh": load_kwh,
            "blink_count": blink_count,
            "start_time": start_time,
            "total_consumed_kwh": total_consumed,
            "total_input_kwh": transformer_data["total_input_kwh"],
            "received_at": current_time
        }), 200

    # -------------------------------------------------------------------------
    # 2. DASHBOARD RETRIEVING DATA (HTTP GET)
    # -------------------------------------------------------------------------
    elif request.method == "GET":
        total_consumed = recalculate_transformer_totals()
        current_time = transformer_data["last_updated"] or datetime.now().strftime("%H:%M:%S")

        # Check if live ESP32 (IN1) has reported yet
        esp32_online = houses_data["IN1"]["status"] == "ONLINE"

        return jsonify({
            "status": "ONLINE" if esp32_online else "WAITING",
            "message": "Telemetry streaming" if esp32_online else "Waiting for ESP32 data...",
            "houses": houses_data,
            "sum_house_kwh": total_consumed,
            "transformer": {
                "transformer_id": transformer_data["transformer_id"],
                "tc_count": transformer_data["tc_count"],
                "total_input_kwh": transformer_data["total_input_kwh"],
                "total_consumed_kwh": total_consumed,
                "capacity_kwh": transformer_data["capacity_kwh"],
                "last_updated": transformer_data["last_updated"] or "--"
            },
            "last_updated": current_time
        }), 200


@app.route("/api/reset", methods=["POST"])
def reset_counter():
    """
    Route: /api/reset (POST)
    Resets the blink counter and energy for a house (defaults to IN1).
    Establishes a new offset baseline and sets a fresh start_time.
    """
    data = request.get_json(silent=True) or {}
    house_id = str(data.get("house_id", "IN1")).strip().upper()
    current_time = datetime.now().strftime("%H:%M:%S")

    if house_id == "ALL":
        for hid, h in houses_data.items():
            h["blink_offset"] = h.get("raw_blink_count", h.get("blink_count", 0))
            h["blink_count"] = 0
            h["load_kwh"] = 0.0
            h["start_time"] = current_time
            h["last_updated"] = f"Reset at {current_time}"
    elif house_id in houses_data:
        h = houses_data[house_id]
        h["blink_offset"] = h.get("raw_blink_count", h.get("blink_count", 0))
        h["blink_count"] = 0
        h["load_kwh"] = 0.0
        h["start_time"] = current_time
        h["last_updated"] = f"Reset at {current_time}"
    else:
        return jsonify({"status": "error", "message": f"House {house_id} not found"}), 404

    total_consumed = recalculate_transformer_totals()
    transformer_data["last_updated"] = current_time

    print(f"[{current_time}] Counter RESET triggered for house {house_id} -> Start Time: {current_time}, Count: 0, Total: {total_consumed} kWh")

    return jsonify({
        "status": "success",
        "message": f"Blink counter for {house_id} reset to 0",
        "house_id": house_id,
        "start_time": current_time,
        "blink_count": 0,
        "load_kwh": 0.0,
        "total_consumed_kwh": total_consumed
    }), 200


if __name__ == "__main__":
    print("==================================================")
    print("   Transformer Energy Monitoring Server (Flask)   ")
    print("==================================================")
    print(" * Port: 5000 (Localhost & Tunnel Ready)")
    print(" * Energy Units: kWh")
    print(f" * Transformer Total Input: {TRANSFORMER_INPUT_KWH} kWh")
    print(" * Web Dashboard: http://localhost:5000")
    print(" * API Endpoint:  /api/data")
    print("==================================================")
    app.run(host="0.0.0.0", port=5000, debug=True)
