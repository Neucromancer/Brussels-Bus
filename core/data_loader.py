import sqlite3
# lấy bảng stop_times từ database
def load_stop_times(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT trip_id, stop_id, arrival_time, departure_time, stop_sequence FROM stop_times")
    rows = cursor.fetchall()

    conn.close()
    return rows

#lấy tọa độ các stop xuát hiện trong bảng stop_times
def load_coordinates_for_used_stops(db_path, stop_times):
  


    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # lấy những stop_id xuất hiện trong stop_times
    stop_ids = list({row[1] for row in stop_times})

    # xấy dựng câu truy vấn và lấy tọa độ từ stops table(tham khảo AI)
    placeholders = ",".join(["?"] * len(stop_ids)) 
    query = f"SELECT stop_id, stop_lat, stop_lon FROM stops WHERE stop_id IN ({placeholders})"

    cursor.execute(query, stop_ids)
    rows = cursor.fetchall()

    conn.close()

    # xây dựng bảng toạ độ :stop_id -> (lat, lon)
    coordinates = {stop_id: (float(lat),float(lon)) for stop_id, lat, lon in rows}

    return coordinates
