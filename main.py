import os
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from mock_vlm import ask_required_information, analyze_with_vlm
import camera_simulator

DB_FILE = "cctv.db"

def init_database():
    # Létező fájl törlése
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Kameraesemények tábla
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS camera_events (
        event_id TEXT PRIMARY KEY,
        camera_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        frame_path TEXT NOT NULL,
        video_path TEXT NOT NULL,
        is_analyzed BOOLEAN NOT NULL
    )
    """)

    # Riasztások tábla
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,         -- Az első riasztást kiváltó esemény ID-ja
        camera_id TEXT NOT NULL,        -- Kamera azonosító
        start_timestamp TEXT NOT NULL,  -- Kezdeti timestamp (az első riasztás pillanata)
        end_timestamp TEXT,             -- Vége timestamp vagy 'ongoing'
        description TEXT NOT NULL,      -- Az első jelzés alapján generált leírás
        FOREIGN KEY (event_id) REFERENCES camera_events (event_id)
    )
    """)

    # Riasztási okok tábla
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_reason (
        reason_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        event_id TEXT NOT NULL,         -- Melyik kameraeseményhez tartozik a fájl
        frame_path TEXT,                -- A kép elérési útvonala (ha van)
        video_path TEXT,                -- A videó elérési útvonala (ha van)
        timestamp TEXT NOT NULL,        -- Az esemény időbélyege
        FOREIGN KEY (alert_id) REFERENCES alerts (alert_id),
        FOREIGN KEY (event_id) REFERENCES camera_events (event_id)
    )
    """)

    conn.commit()
    conn.close()
    print(f"Az adatbázis sikeresen létrejött: {DB_FILE}")

def background_simulator_runner():
    print("Kamera szimulátor elindult")
    
    first_event = camera_simulator.get_next_simulation_step()
    if not first_event:
        return

    delay = first_event[3]
    time.sleep(delay)
    camera_simulator.send_event_to_db(first_event)

    while True:
        next_event = camera_simulator.get_next_simulation_step()
        if not next_event:
            break
        
        delay = next_event[3]
        time.sleep(delay)
        camera_simulator.send_event_to_db(next_event)

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_dynamic_context(cursor, camera_id: str, current_timestamp: str, requirement: dict):
    need_type = requirement["need_type"]
    max_seconds = requirement.get("max_time_window_seconds", 0)

    try:
        curr_dt = datetime.strptime(current_timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        curr_dt = datetime.now()

    if need_type == "frame":
        limit = 1
        window_start_dt = curr_dt
    elif need_type == "video":
        limit = 1
        window_start_dt = curr_dt
    elif need_type == "multi_video":
        limit = 10
        window_start_dt = curr_dt - timedelta(seconds=max_seconds)
    else:
        return []

    window_start_str = window_start_dt.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT event_id, camera_id, event_type, timestamp, frame_path, video_path
        FROM camera_events
        WHERE camera_id = ? 
          AND timestamp <= ? 
          AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (camera_id, current_timestamp, window_start_str, limit))

    rows = cursor.fetchall()
    events = [dict(row) for row in reversed(rows)]

    if need_type == "frame":
        for ev in events:
            ev['video_path'] = None

    elif need_type == "video" and len(events) > 0:
        events = [events[-1]]
        for ev in events:
            ev['frame_path'] = None

    elif need_type == "multi_video" and len(events) > 0:
        for ev in events:
            ev['frame_path'] = None

    # Konkrét átadott kontextusok kiírása
    print(f"Átadott kontextusok ({need_type}):")
    if not events:
        print("Nincsen átadott kontextus")
    else:
        for idx, ev in enumerate(events, 1):
            if need_type == "frame":
                print(
                    f"{idx}. [FRAME] Fájl: {ev.get('frame_path')} | Időpont:"
                    f" {ev.get('timestamp')}"
                )
            elif need_type == "video":
                print(
                    f"{idx}. [VIDEO] Fájl: {ev.get('video_path')} | Időpont:"
                    f" {ev.get('timestamp')}"
                )
            elif need_type == "multi_video":
                print(
                    f"{idx}. [MULTI_VIDEO] Esemény ID: {ev.get('event_id')} | Videó:"
                    f" {ev.get('video_path')} |"
                    f" Időpont: {ev.get('timestamp')}"
                )

    return events

def process_alerts_and_reasons(cursor, event_dict, vlm_result, context_events):
    event_id = event_dict['event_id']
    camera_id = event_dict['camera_id']
    current_timestamp = event_dict['timestamp']
    curr_dt = datetime.strptime(current_timestamp, "%Y-%m-%d %H:%M:%S")

    # Adott kamerán az utolsó riasztás megkeresése
    cursor.execute("""
        SELECT alert_id, start_timestamp, end_timestamp, description 
        FROM alerts
        WHERE camera_id = ?
        ORDER BY end_timestamp DESC
        LIMIT 1
    """, (camera_id,))
    last_alert = cursor.fetchone()

    active_alert_id = None

    if vlm_result["triggered"]:
        if last_alert:
            last_end_str = last_alert['end_timestamp']
            try:
                last_dt = datetime.strptime(last_end_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                last_dt = curr_dt

            time_diff = (curr_dt - last_dt).total_seconds()

            if 0 <= time_diff <= 15:
                active_alert_id = last_alert['alert_id']
                print(f"Meglévő riasztás kiterjesztése: Alert ID: {active_alert_id} | Új end_timestamp: {current_timestamp}")
                
                cursor.execute("""
                    UPDATE alerts
                    SET end_timestamp = ?
                    WHERE alert_id = ?
                """, (current_timestamp, active_alert_id))

        if not active_alert_id:
            print(f"RIASZTÁS! Indoklás: {vlm_result['description']}")
            cursor.execute("""
                INSERT INTO alerts (event_id, camera_id, start_timestamp, end_timestamp, description)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, camera_id, current_timestamp, current_timestamp, vlm_result["description"]))
            
            cursor.execute("SELECT last_insert_rowid() as id")
            active_alert_id = cursor.fetchone()['id']

        # Riasztási ok mentése duplikáció nélkül
        for ctx_ev in context_events:
            ctx_event_id = ctx_ev['event_id']
            ctx_frame = ctx_ev.get('frame_path')
            ctx_video = ctx_ev.get('video_path')
            ctx_time = ctx_ev['timestamp']

            cursor.execute("""
                SELECT reason_id FROM alert_reason
                WHERE alert_id = ? AND event_id = ?
            """, (active_alert_id, ctx_event_id))
            existing_reason = cursor.fetchone()

            if not existing_reason:
                cursor.execute("""
                    INSERT INTO alert_reason (alert_id, event_id, frame_path, video_path, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (active_alert_id, ctx_event_id, ctx_frame, ctx_video, ctx_time))

    else:
        print(f"Nincs riasztás az eseményhez. ({vlm_result['description']})")

def main_loop():
    print("=== CCTV Backend ===")
    
    # Felhasználói prompt bekérése
    user_prompt = input("Add meg a riasztási feltételt (pl. 'Jelezz, ha füstöt látsz'): ")
    if not user_prompt.strip():
        user_prompt = "Jelezz, ha füstöt vagy mozgást látsz"
        print(f"Nem adtál meg promptot, az alapértelmezett: '{user_prompt}'")

    print(f"\nA rendszer elindult. Aktív prompt: '{user_prompt}'\n")

    # Milyen kontextus szükséges a prompt eldöntésére
    requirement = ask_required_information(user_prompt)
    print(f"Szükséges kontextus: Típus: {requirement['need_type']} | Max időablak: {requirement.get('max_time_window_seconds', 0)}mp")
    print(f"Indoklás: {requirement['reasoning']}\n")

    # Nincs elég információ
    if requirement["need_type"] == "insufficient_info":
        print(f"A megadott prompt eldöntéséhez a rendszer nem rendelkezik elegendő információval.")
        print("Kérlek, indítsd újra a programot egy másik feltétellel.")
        return

    # Kamera szimulátor elindítása
    sim_thread = threading.Thread(target=background_simulator_runner, daemon=True)
    sim_thread.start()

    try:
        while True:
            conn = get_connection()
            cursor = conn.cursor()

            # Még nem viszgált események
            cursor.execute("""
                SELECT event_id, camera_id, event_type, timestamp, frame_path, video_path
                FROM camera_events
                WHERE is_analyzed = 0
                ORDER BY timestamp ASC
            """)
            unanalysed_events = cursor.fetchall()

            if not unanalysed_events:
                conn.close()
                time.sleep(2)
                continue

            for event in unanalysed_events:
                event_dict = dict(event)
                event_id = event_dict['event_id']
                camera_id = event_dict['camera_id']
                current_timestamp = event_dict['timestamp']

                print(f"Új esemény feldolgozása: {event_id} (Kamera: {camera_id}, Típus: {event_dict['event_type']})")

                context_events = fetch_dynamic_context(cursor, camera_id, current_timestamp, requirement)

                vlm_result = analyze_with_vlm(user_prompt, context_events, requirement)

                process_alerts_and_reasons(cursor, event_dict, vlm_result, context_events)

                cursor.execute("""
                    UPDATE camera_events
                    SET is_analyzed = 1
                    WHERE event_id = ?
                """, (event_id,))

                conn.commit()
                
            conn.close()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nA program futása a felhasználó által megszakítva.")

if __name__ == "__main__":
        init_database()
        main_loop()