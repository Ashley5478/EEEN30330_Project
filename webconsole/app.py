#!/usr/bin/env python3
"""Rainer Web — Flask frontend for the Rainer IoT server."""

import json
import socket
import ssl
import os
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

app = Flask(__name__)
app.secret_key = os.urandom(24)  # session encryption key

# ── Crypto ────────────────────────────────────────────────────────────────────
CR_KEY=bytes.fromhex("<PLEASE PASTE THE SAME CR_KEY FROM THE rainer.py>")

def challenge_response(seed: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(CR_KEY), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(seed) + enc.finalize()

# ── Constants ─────────────────────────────────────────────────────────────────
COMMAND_QUERY         = 0
COMMAND_SET_MODE      = 1
COMMAND_SET_PUMP      = 2
COMMAND_SET_THRESHOLD = 3
COMMAND_SET_INTERVAL  = 4
COMMAND_SET_DURATION  = 5
MODE_AUTOMATIC        = 0
MODE_MANUAL           = 1
UINT16_MAX            = 65535

SSL_CERT_PATH = "../rainer.pem"   # ← adjust path if needed

# ── Socket helper ─────────────────────────────────────────────────────────────
def send_command(host: str, port: int, command_data: dict) -> dict:
    """
    Open a TLS connection, perform challenge-response auth, send one command,
    return the parsed JSON response.  Raises on any error.
    """
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.load_verify_locations(SSL_CERT_PATH)
    ssl_ctx.check_hostname = False

    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(8)
    raw.connect((host, port))
    s = ssl_ctx.wrap_socket(raw, server_hostname=host)

    # Receive 16-byte challenge seed
    seed = b""
    while len(seed) < 16:
        seed += s.recv(16 - len(seed))

    # Send AES response
    s.sendall(challenge_response(seed))

    # Auth result
    auth_raw = s.recv(256)
    try:
        auth = json.loads(auth_raw.decode().strip())
    except Exception:
        auth = {"raw": auth_raw.decode(errors="replace")}

    # Send our command
    payload = (json.dumps(command_data) + '\n').encode()
    s.sendall(payload)

    # Receive device response
    resp_raw = s.recv(1024)
    s.close()

    try:
        resp = json.loads(resp_raw.decode().strip())
    except Exception:
        resp = {"raw": resp_raw.decode(errors="replace")}

    return {"auth": auth, "response": resp}


def test_connection(host: str, port: int) -> bool:
    """Quick connectivity smoke-test (challenge-response + query)."""
    try:
        send_command(host, port, {"command": COMMAND_QUERY})
        return True
    except Exception:
        return False


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/connect", methods=["POST"])
def connect():
    host = request.form.get("host", "").strip()
    port_str = request.form.get("port", "").strip()

    if not host or not port_str:
        return render_template("index.html", error="Host and port are required.")

    try:
        port = int(port_str)
    except ValueError:
        return render_template("index.html", error=f"Invalid port: {port_str}")

    if not test_connection(host, port):
        return render_template(
            "index.html",
            error=f"Could not connect to {host}:{port}. Check the address and that the device is online.",
            host=host, port=port_str,
        )

    session["host"] = host
    session["port"] = port
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    if "host" not in session:
        return redirect(url_for("index"))
    return render_template("dashboard.html", host=session["host"], port=session["port"])


@app.route("/api/command", methods=["POST"])
def api_command():
    if "host" not in session:
        return jsonify({"error": "Not connected"}), 403

    body = request.get_json(force=True)
    cmd_type = body.get("command")

    if cmd_type == COMMAND_QUERY:
        data = {"command": COMMAND_QUERY}

    elif cmd_type == COMMAND_SET_MODE:
        mode = body.get("mode")
        if mode not in (MODE_AUTOMATIC, MODE_MANUAL):
            return jsonify({"error": "Invalid mode"}), 400
        data = {"command": COMMAND_SET_MODE, "mode": mode}

    elif cmd_type == COMMAND_SET_PUMP:
        index = body.get("index")
        status = body.get("status")
        if index is None or status is None:
            return jsonify({"error": "index and status required"}), 400
        data = {"command": COMMAND_SET_PUMP, "index": int(index), "status": bool(status)}

    elif cmd_type == COMMAND_SET_THRESHOLD:
        index = body.get("index")
        t_type = body.get("type")
        value = body.get("value")
        if index is None or t_type not in ("high", "low") or value is None:
            return jsonify({"error": "index, type (high/low), and value required"}), 400
        value = int(value)
        if not (0 <= value <= UINT16_MAX):
            return jsonify({"error": f"value must be 0-{UINT16_MAX}"}), 400
        data = {"command": COMMAND_SET_THRESHOLD, "index": int(index), "type": t_type, "value": value}

    elif cmd_type == COMMAND_SET_INTERVAL:
        interval = body.get("interval")
        if interval is None:
            return jsonify({"error": "interval required"}), 400
        data = {"command": COMMAND_SET_INTERVAL, "interval": int(interval)}

    elif cmd_type == COMMAND_SET_DURATION:
        duration = body.get("duration")
        if duration is None:
            return jsonify({"error": "duration required"}), 400
        data = {"command": COMMAND_SET_DURATION, "duration": int(duration)}

    else:
        return jsonify({"error": "Unknown command"}), 400

    try:
        result = send_command(session["host"], session["port"], data)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/disconnect")
def disconnect():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
