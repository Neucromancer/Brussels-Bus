import os
import sys
import sqlite3
import pandas as pd
# --- BƯỚC 1: CẤU HÌNH ĐƯỜNG DẪN ---
# 1. Tìm đường dẫn đến thư mục 'src'
# __file__ là db_manager.py, dirname là data_engine, dirname của nó là src
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.dirname(current_dir) 

# 2. Thêm 'src' vào danh sách tìm kiếm của Python
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 3. BÂY GIỜ MỚI IMPORT (Phải có data_engine. ở trước)
from data_engine.data_process import load_data
from logic.models import Stop, NextStopInfo

# --- BƯỚC 2: CẤU HÌNH ĐƯỜNG DẪN DATABASE ---
DB_PATH = os.path.join(current_dir, "stib_database.db")

def get_data_from_db():
    """Kết nối và lấy DataFrame thô từ SQL"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"❌ Không tìm thấy file database tại: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT * FROM route_paths"
        df = pd.read_sql_query(query, conn)
        return df
    finally:
        conn.close()

# --- BƯỚC 3: CHẠY TEST ---
if __name__ == "__main__":
    try:
        print("--- 1. Đang lấy dữ liệu từ SQLite ---")
        df_raw = get_data_from_db()
        print(f"✅ Đã lấy {len(df_raw)} dòng.")

        print("\n--- 2. Đang chuyển đổi sang Object (via data_processing) ---")
        stops_list = load_data(df_raw)
        
        print(f"\n--- 3. KẾT QUẢ TEST: 10 BẾN ĐẦU TIÊN ---")
        # Chỉ lấy 10 bến đầu để in
        sample_stops = stops_list[:10]
        
        for i, stop in enumerate(sample_stops, 1):
            print(f"\n[{i}] Bến: {stop.name} (ID: {stop.id})")
            print(f"    Tọa độ: ({stop.lat}, {stop.lon})")
            
            if not stop.next_stops:
                print("    ⚠️ Cảnh báo: Bến này không có đường đi tiếp")
            else:
                print(f"    Số lượng bến kế tiếp: {len(stop.next_stops)}")
                for connection in stop.next_stops:
                    print(f"      --> Tới: {connection.stop.name} (Tuyến: {connection.route_id}, {connection.travel_time}p)")

    except Exception as e:
        print(f"❌ Lỗi hệ thống: {e}")