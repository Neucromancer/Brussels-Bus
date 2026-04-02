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
    Chỉ lấy những điểm dừng có trong stop_times
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # lấy những stopid có trong stop_times, lọc trùng nhau 
    stop_ids = list({row[1] for row in stop_times})

    # build SQL IN clause safely
       #tham khảo AI
    placeholders = ",".join(["?"] * len(stop_ids))  #tạo chuỗi "?,?,...." độ dài bằng số stop_ids
    query = f"SELECT stop_id, stop_lat, stop_lon FROM stops WHERE stop_id IN ({placeholders})"  
    #tạo câu truy vấn


    
    #lấy stopid, tọa độ của stopid 
    cursor.execute(query, stop_ids)   # python sẽ thay chuỗi "?" bằng dữ liệu thật
    rows = cursor.fetchall()

    conn.close()

    # tạo danh sách stop_ids và tọa độ:  stop_id -> (lat, lon)
    coordinates = {stop_id: (float(lat),float(lon)) for stop_id, lat, lon in rows}

    return coordinates
