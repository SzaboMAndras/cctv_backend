import sqlite3
from datetime import datetime

DB_FILE = "cctv.db"

SIMULATION_SCENARIO = 1

# SIMULATION_EVENTS = [event_id: inkrementálisan növekvő, camera_id: minden kamerának egyedi, event_type: ami alapján a kamera eseményt rögzített, time: az esemény rögzítése előtti várakozás másodpercekben]

if SIMULATION_SCENARIO == 1:
    SIMULATION_EVENTS = [
        ("1", "1", "smoke", 3),
        ("2", "1", "smoke", 10),
    ]
elif SIMULATION_SCENARIO == 2:
    SIMULATION_EVENTS = [
        ("1", "1", "car", 3),
        ("2", "2", "car", 10),
    ]
elif SIMULATION_SCENARIO == 3:
    SIMULATION_EVENTS = [
        ("1", "1", "movement", 3),
        ("2", "1", "movement", 10),
        ("3", "1", "person", 10),
    ]
elif SIMULATION_SCENARIO == 4:
    SIMULATION_EVENTS = [
        ("1", "1", "person", 3),
        ("2", "1", "person", 10),
        ("3", "1", "person", 10),
        ("4", "1", "person", 10),
        ("5", "1", "person", 10),
    ]

elif SIMULATION_SCENARIO == 5:
    SIMULATION_EVENTS = [

    ]

# Szimuláció indexe
_current_event_index = 0

def get_next_simulation_step():
    global _current_event_index
    if _current_event_index < len(SIMULATION_EVENTS):
        event = SIMULATION_EVENTS[_current_event_index]
        _current_event_index += 1
        return event
    return None

def send_event_to_db(event_data):
    event_id, camera_id, event_type, _ = event_data
    
    now = datetime.now()
    current_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    file_timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    
    frame_path = f"data/frames/{camera_id}_{file_timestamp_str}.jpg"
    video_path = f"data/videos/{camera_id}_{file_timestamp_str}.MJPEG"

    is_analyzed = 0

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO camera_events (event_id, camera_id, event_type, timestamp, frame_path, video_path, is_analyzed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_id, camera_id, event_type, current_timestamp, frame_path, video_path, is_analyzed))
        conn.commit()
        print(f"\nÚj kameraesemény: ID: {event_id} | Kamera: {camera_id} | Típus: {event_type} | Idő: {current_timestamp}")
    except Exception as e:
        print(f"[Szimulátor hiba: {e}")
    finally:
        conn.close()