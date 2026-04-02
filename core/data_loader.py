import sqlite3

def load_stop_times(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT trip_id, stop_id, arrival_time, departure_time, stop_sequence FROM stop_times")
    rows = cursor.fetchall()

    conn.close()
    return rows


def load_coordinates_for_used_stops(db_path, stop_times):
    """
    Load ONLY coordinates for stops that appear in stop_times
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # extract unique stop_ids from stop_times
    stop_ids = list({row[1] for row in stop_times})

    # build SQL IN clause safely
    placeholders = ",".join(["?"] * len(stop_ids))
    query = f"SELECT stop_id, stop_lat, stop_lon FROM stops WHERE stop_id IN ({placeholders})"

    cursor.execute(query, stop_ids)
    rows = cursor.fetchall()

    conn.close()

    # build dict: stop_id -> (lat, lon)
    coordinates = {stop_id: (float(lat),float(lon)) for stop_id, lat, lon in rows}

    return coordinates
