from flask import Flask, request, jsonify, send_file
from flask_sock import Sock
import datetime
import threading
import time
import json
from termcolor import colored
from main import BusylightController
import sys
import sqlite3
import csv
import getpass
import os
import socket

app = Flask(__name__)
sock = Sock(app)
bs = BusylightController()

# Initialize default configurations
duration = 10 * 60  # 10 minutes
inactive_mins = 10 * 60  # 10 minutes

last_call_time = datetime.datetime.now()
lock = threading.Lock()
countdown_event = threading.Event()

user_active = False  # This will track if there's an ongoing user activity
ADMIN_TOKEN = "UPa2KJ1llHD2PgnU"  # Replace with a secure token

def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect('activity_log.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 timestamp TEXT,
                 username TEXT,
                 event_type TEXT,
                 duration INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config (
                 key TEXT PRIMARY KEY,
                 value INTEGER)''')
    conn.commit()
    conn.close()

def load_config():
    """Load configurations from the database."""
    global duration, inactive_mins
    conn = sqlite3.connect('activity_log.db')
    c = conn.cursor()
    c.execute("SELECT key, value FROM config")
    rows = c.fetchall()
    conn.close()
    config = {row[0]: row[1] for row in rows}
    duration = config.get('duration', 10 * 60)  # Default to 10 minutes if not set
    inactive_mins = config.get('inactive_mins', 10 * 60)  # Default to 10 minutes if not set

def save_config(key, value):
    """Save a configuration to the database."""
    conn = sqlite3.connect('activity_log.db')
    c = conn.cursor()
    c.execute("REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

@app.route('/update_config', methods=['POST'])
def update_config():
    token = request.headers.get('Authorization')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized access'}), 401

    data = request.json
    global duration, inactive_mins
    if 'duration' in data:
        duration = int(data['duration'])
        save_config('duration', duration)
    if 'inactive_mins' in data:
        inactive_mins = int(data['inactive_mins'])
        save_config('inactive_mins', inactive_mins)

    return jsonify({'status': 'success', 'duration': duration, 'inactive_mins': inactive_mins})

@app.route('/generate_report', methods=['GET'])
def generate_report_endpoint():
    token = request.headers.get('Authorization')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized access'}), 401
    
    file_name = generate_report()
    return send_file(file_name, as_attachment=True)

@app.route('/user_info', methods=['GET'])
def user_info():
    token = request.headers.get('Authorization')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized access'}), 401

    username = getpass.getuser()
    local_ip = get_local_ip()
    
    return jsonify({'username': username, 'local_ip': local_ip})

def get_local_ip():
    """Get the local IP address of the computer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

def log_event(event_type, duration):
    """Log an event to the SQLite database with the event type, duration, and username."""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = getpass.getuser()
    with lock:
        conn = sqlite3.connect('activity_log.db')
        c = conn.cursor()
        c.execute("INSERT INTO logs (timestamp, username, event_type, duration) VALUES (?, ?, ?, ?)",
                  (current_time, username, event_type, duration))
        conn.commit()
        conn.close()

def format_duration(total_seconds):
    """Convert seconds to a formatted string HH:MM:SS."""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'

def generate_report():
    """Generate a comprehensive report with daily, weekly, and monthly sections and save it to a CSV file."""
    current_time = datetime.datetime.now()
    report_data = {
        'daily': current_time - datetime.timedelta(days=1),
        'weekly': current_time - datetime.timedelta(weeks=1),
        'monthly': current_time - datetime.timedelta(days=30)
    }

    file_name = 'activity_report.csv'
    aggregated_data = {'daily': {}, 'weekly': {}, 'monthly': {}}

    conn = sqlite3.connect('activity_log.db')
    c = conn.cursor()
    
    for time_frame, start_time in report_data.items():
        c.execute("SELECT username, event_type, SUM(duration), timestamp FROM logs WHERE timestamp >= ? GROUP BY username, event_type",
                  (start_time.strftime("%Y-%m-%d %H:%M:%S"),))
        rows = c.fetchall()
        for row in rows:
            username, event_type, total_duration, timestamp = row
            if username not in aggregated_data[time_frame]:
                aggregated_data[time_frame][username] = {}
            if event_type not in aggregated_data[time_frame][username]:
                aggregated_data[time_frame][username][event_type] = {'duration': 0, 'timestamp': timestamp}
            aggregated_data[time_frame][username][event_type]['duration'] += total_duration

    conn.close()

    # Write the aggregated data to a single CSV file
    with open(file_name, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Report Type', 'Username', 'Event Type', 'Total Duration', 'Day of Week', 'Week of Year', 'Month', 'Year'])

        for time_frame, users in aggregated_data.items():
            writer.writerow([f'{time_frame.capitalize()} Report'])
            for username, events in users.items():
                for event_type, data in events.items():
                    total_duration = data['duration']
                    timestamp = datetime.datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
                    day_of_week = timestamp.strftime('%A')
                    week_of_year = timestamp.strftime('%U')
                    month = timestamp.strftime('%B')
                    year = timestamp.strftime('%Y')
                    writer.writerow(['', username, event_type, format_duration(total_duration), day_of_week, week_of_year, month, year])

    return file_name

def countdown_worker(status, ws):
    global last_call_time, user_active

    start_time = time.time()
    countdown_event.clear()  # Ensure the event is clear at the start

    while not countdown_event.is_set():
        elapsed = time.time() - start_time

        

        time_left = max(duration - elapsed, 0)

        if time_left <= 0:
            send_countdown_completion(ws, status, int(elapsed // 60),int(elapsed % 60))
            break

        try:
            ws.send(json.dumps({
                'type': 'countdown_update',
                'status': str(status).capitalize(),
                'minutes': int(elapsed // 60),
                'seconds': int(elapsed % 60)
            }))
            time.sleep(1)  # Update every second
        except Exception as e:
            print(f"WebSocket send error: {e}")
            with lock:
                last_call_time = datetime.datetime.now()  # Reset last call time 
            break

    manage_user_activity(status, False)
    log_event(status, duration)  # Log the event after completion

def send_countdown_completion(ws, status,min,secs):
    try:
        ws.send(json.dumps({'type': 'countdown_completed', 'status': str(status).capitalize(), 'minutes': min, 'seconds': secs}))
    except Exception as e:
        print(f"WebSocket send error on completion: {e}")

def manage_countdown(status, ws):
    global countdown_event
    countdown_event.set()  # Signal any existing thread to stop
    time.sleep(1)  #  buffer to ensure the thread stops

    color = bs.parse_color(status)  # Set the light color
    light_resp = bs.send_request("light", color)
    if light_resp.status_code == 200:
        print(colored(f"Busylight set to {status}", "green"))
    else:
        print(colored(f"Error setting busylight for {status}: {light_resp.status_code}","red"))

    countdown_event.clear()  # Reset for new usage
    threading.Thread(target=countdown_worker, args=(status, ws)).start()

def update_inactivity_countdown(seconds_to_inactivity):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    output = f"\r[INFO] {current_time} | Countdown to inactivity: {seconds_to_inactivity:6.1f} seconds remaining. Activity {user_active} | "
   
    sys.stdout.write(colored(output, "cyan"))
    sys.stdout.flush()  # Ensure the output is immediately visible

def check_inactivity():
    global last_call_time, user_active
    while True:
        time.sleep(1)  # Check state every second
        with lock:
            time_elapsed = datetime.datetime.now() - last_call_time

        seconds_to_inactivity = inactive_mins - time_elapsed.total_seconds()
        if seconds_to_inactivity > 0:
            update_inactivity_countdown(seconds_to_inactivity)
        else:
            if not user_active:
                set_busylight_inactive()
                log_event('inactivity', inactive_mins)  # Log inactivity event
                print(colored("Busylight set to inactive due to inactivity.", "red"))
            with lock:
                last_call_time = datetime.datetime.now()  # Reset last call time after setting busylight inactive

def set_busylight_inactive():
    color = bs.parse_color("no call")
    light_resp = bs.send_request("light", color)
    if light_resp.status_code == 200:
        print(colored("Busylight set to inactive red", "red"))
    else:
        print(colored(f"Error setting busylight to inactive: {light_resp.status_code}", "red"))

def manage_user_activity(status, is_active):
    global user_active, last_call_time
    with lock:
        user_active = is_active
        if is_active:
            last_call_time = datetime.datetime.now()  # Reset the last call time whenever an activity starts or stops

@sock.route('/ws')
def websocket(ws):
    global last_call_time
    while True:
        data = ws.receive()
        if data:
            try:
                json_data = json.loads(data)
                print(json_data)

                status = json_data.get("status")

                if status == "call_in_progress":
                    status = "on call"
                    handle_on_call(ws, status)
                    manage_user_activity(status, True)
                    
                elif status == "on_opportunity_page":
                    handle_on_opportunity_page(ws, status)
                    manage_user_activity(status, True)

                elif status in ["break", "invoice"]:
                    # Reset the last_call_time when user is actively setting a break or invoice
                    with lock:
                        last_call_time = datetime.datetime.now()
                    manage_countdown(status, ws)
                    manage_user_activity(status, True)

                else:
                    manage_user_activity(status, False)
                    
            except json.JSONDecodeError:
                print("Received invalid JSON data")
        else:
            break

def handle_on_call(ws, status):
    global last_call_time
    countdown_event.set()  # Stop any active countdown
    color = bs.parse_color(status)
    light_resp = bs.send_request("light", color)
    if light_resp.status_code == 200:
        ws.send(f'Echo: {json.dumps({"status": "on call"})}')
        with lock:
            last_call_time = datetime.datetime.now()  # Reset the last call time for "on call"
        print(colored(f"Busylight set to {status}", "green"))
    else:
        print(colored(f"Error setting busylight for {status}: {light_resp.status_code}", "red"))


def handle_on_opportunity_page(ws, status):
    global last_call_time
    countdown_event.set()  # Stop any active countdown
    color = bs.parse_color("opportunity")  # Assuming a specific color for Opportunity page
    light_resp = bs.send_request("light", color)
    if light_resp.status_code == 200:
        ws.send(f'Echo: {json.dumps({"status": "on_opportunity_page"})}')
        with lock:
            last_call_time = datetime.datetime.now()  # Reset the last activity time
        print(colored(f"Busylight set to {status}", "green"))
    else:
        print(colored(f"Error setting busylight for {status}: {light_resp.status_code}", "red"))

@app.route('/')
def index():
    return 'WebSocket server is running.'

if __name__ == '__main__':
    init_db()  # Initialize the database
    load_config()  # Load configurations from the database
    threading.Thread(target=check_inactivity, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
