from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for, session
from flask_socketio import SocketIO, emit
import requests
import socket
import threading
import random
import string
import os
import time
import io

app = Flask(__name__)
app.secret_key = "58ac19c0716508645480f02b"
socketio = SocketIO(app)

ADMIN_TOKEN = "UPa2KJ1llHD2PgnU"
user_info_dict = {}
lock = threading.Lock()
ADMIN_PASSWORD = 'jacko123'  # Replace with a strong password

# Global event to control the network scan thread
network_scan_event = threading.Event()
network_scan_thread = None

def get_local_ip():
    """Get the local IP address of the computer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

def scan_network():
    """Scan the local network for IP addresses and get user info."""
    global user_info_dict
    local_ip = get_local_ip()
    network_prefix = local_ip.rsplit('.', 1)[0]

    for i in range(1, 255):
        if network_scan_event.is_set():
            print("Network scan stopped.")
            break

        ip = f"{network_prefix}.{i}"
        if ip.startswith("127."):
            continue  # Skip loopback addresses
        
        # Emit the current IP being scanned
        socketio.emit('scan_progress', {'ip': ip})
        
        url = f"http://{ip}:5000/user_info"
        headers = {'Authorization': ADMIN_TOKEN}

        try:
            response = requests.get(url, headers=headers, timeout=2)
            if response.status_code == 200:
                user_info = response.json()
                with lock:
                    user_info_dict[ip] = user_info
                print(f"IP: {ip} - Username: {user_info['username']}")
                socketio.emit('scan_update', {'ip': ip, 'username': user_info['username']})
            else:
                print(f"Failed to retrieve user info from {ip}: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to {ip}: {e}")

def generate_report(ip):
    """Generate the report for a specific IP address."""
    url = f"http://{ip}:5000/generate_report"
    headers = {'Authorization': ADMIN_TOKEN}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return io.BytesIO(response.content)
    else:
        return None

def update_config(ip, config_data):
    """Update the configuration on the specified IP address."""
    url = f"http://{ip}:5000/update_config"
    headers = {'Authorization': ADMIN_TOKEN}
    response = requests.post(url, headers=headers, json=config_data)
    if response.status_code == 200:
        return f"Configurations updated successfully on {ip}."
    else:
        return f"Failed to update configurations on {ip}: {response.status_code} - {response.text}"

@app.route('/')
def index():
    """Render the main interface for the admin."""
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Render the login page and handle login."""
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout the user and redirect to login page."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/scan_network')
def scan_network_endpoint():
    """Endpoint to scan the network."""
    global network_scan_thread
    # Set the event to stop any running network scan thread
    if network_scan_thread and network_scan_thread.is_alive():
        network_scan_event.set()
        network_scan_thread.join()
    # Clear the event for the new thread
    network_scan_event.clear()

    # Start a new network scan thread
    network_scan_thread = threading.Thread(target=scan_network)
    network_scan_thread.start()

    return jsonify({'message': 'Network scan started.'})

@app.route('/get_users')
def get_users():
    """Endpoint to get the current user information."""
    with lock:
        users = user_info_dict.items()
    return jsonify([{ 'ip': ip, 'username': info['username'] } for ip, info in users])

@app.route('/generate_report', methods=['GET'])
def generate_report_endpoint():
    """Endpoint to generate report for a specific IP."""
    ip = request.args.get('ip')
    if ip:
        report = generate_report(ip)
        if report:
            return send_file(report, as_attachment=True, download_name=f"{ip}_activity_report.csv", mimetype='text/csv')
        else:
            return jsonify({'error': 'Failed to generate report.'}), 500
    else:
        return jsonify({'error': 'IP address is required.'}), 400

@app.route('/update_config', methods=['POST'])
def update_config_endpoint():
    """Endpoint to update configuration for a specific IP."""
    ip = request.args.get('ip')
    data = request.json
    if ip and data:
        message = update_config(ip, data)
        return jsonify({'message': message})
    else:
        return jsonify({'error': 'IP address and configuration data are required.'}), 400

@app.route('/update_config_all', methods=['POST'])
def update_config_all_endpoint():
    """Endpoint to update configuration for all users."""
    data = request.json
    if data:
        messages = []
        for ip in user_info_dict:
            messages.append(update_config(ip, data))
        return jsonify({'message': 'Config update complete for all users.', 'details': messages})
    else:
        return jsonify({'error': 'Configuration data is required.'}), 400

def periodically_scan_net():
    while True:
        scan_network()
        time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=periodically_scan_net, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5001)


# nuitka busylight_server.py --standalone --follow-imports --output-dir=build --assume-yes-for-downloads