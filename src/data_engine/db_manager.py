import os
import sys
import sqlite3
import pandas as pd
import zipfile

# --- BƯỚC 1: CẤU HÌNH ĐƯỜNG DẪN ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # src/data_engine
src_path = os.path.dirname(current_dir)                  # src
base_dir = os.path.dirname(src_path)                     # BRUSSELS-BUS (Thư mục gốc)

if src_path not in sys.path:
    sys.path.insert(0, src_path)

# --- BƯỚC 2: CẤU HÌNH ĐƯỜNG DẪN DATABASE & DATA ---
DATA_DIR = os.path.join(base_dir, "data")
ZIP_PATH = os.path.join(DATA_DIR, "brussels_gtfs.zip")
EXTRACT_DIR = os.path.join(DATA_DIR, "gtfs_raw")

# Đưa file DB ra thư mục data ngoài cùng để file core/data_loader.py của Nhóm 1 dễ dàng chắp nối
DB_PATH = os.path.join(DATA_DIR, "stib_database.db")

def build_database():
    """Giải nén file GTFS và nạp dữ liệu vào SQLite cho thuật toán A*"""
    if not os.path.exists(ZIP_PATH):
        raise FileNotFoundError(f"❌ Không tìm thấy file zip tại {ZIP_PATH}. Hãy chạy api_client.py để tải data trước!")

    print("--- 1. Đang giải nén dữ liệu GTFS ---")
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    print("✅ Giải nén xong.")

    print("\n--- 2. Đang tạo database SQLite ---")
    conn = sqlite3.connect(DB_PATH)

    try:
        # Nạp bảng stops (chứa tọa độ lat, lon cho hàm heuristic)
        print("-> Đang nạp bảng 'stops'...")
        stops_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stops.txt"))
        stops_df.to_sql("stops", conn, if_exists="replace", index=False)

        # Nạp bảng stop_times (chứa lịch trình di chuyển cho thuật toán A*)
        print("-> Đang nạp bảng 'stop_times' (Sẽ mất vài phút vì file rất nặng)...")
        stop_times_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stop_times.txt"), low_memory=False)
        stop_times_df.to_sql("stop_times", conn, if_exists="replace", index=False)
        
    except Exception as e:
        print(f"❌ Lỗi khi đọc file TXT: {e}")
    finally:
        conn.close()
        
    print(f"✅ Hoàn tất! Database đã được lưu tại: {DB_PATH}")

def test_database():
    """Kiểm tra xem database đã có dữ liệu chuẩn form Nhóm 1 cần chưa"""
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        print("\n--- 3. TEST KẾT QUẢ DATABASE ---")
        
        # Đếm số lượng bến xe
        stops_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM stops", conn).iloc[0]['cnt']
        print(f"✅ Bảng 'stops' có: {stops_count} dòng.")
        
        # Đếm số lượng lịch trình
        stop_times_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM stop_times", conn).iloc[0]['cnt']
        print(f"✅ Bảng 'stop_times' có: {stop_times_count} dòng.")

        # In thử 5 bến đầu tiên khớp với field mà Nhóm 1 gọi
        print("\nPreview 5 bến đầu tiên (stop_id, stop_lat, stop_lon):")
        preview_df = pd.read_sql_query("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops LIMIT 5", conn)
        print(preview_df)

    except Exception as e:
        print(f"❌ Lỗi khi test: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        build_database()
        test_database()
    except Exception as e:
        print(f"❌ Lỗi hệ thống: {e}")