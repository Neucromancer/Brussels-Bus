import os
import sys
import sqlite3
import pandas as pd
import zipfile

# I. ĐƯỜNG DẪN THƯ MỤC

# --- BƯỚC 1: CẤU HÌNH ĐƯỜNG DẪN ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # \Brussels Bus\src\data_engine
src_path = os.path.dirname(current_dir)                  # \Brussels Bus\src
base_dir = os.path.dirname(src_path)                     # \BRUSSELS-BUS

# --- BƯỚC 2: CẤU HÌNH ĐƯỜNG DẪN DATABASE & DATA ---
DATA_DIR = os.path.join(base_dir, "data")                # \BRUSSELS-BUS\data                    (nơi lưu file zip và database)
ZIP_PATH = os.path.join(DATA_DIR, "brussels_gtfs.zip")   # \BRUSSELS-BUS\data\brussels_gtfs.zip  (nơi lưu file zip sau khi tải về)
EXTRACT_DIR = os.path.join(DATA_DIR, "gtfs_raw")         # \BRUSSELS-BUS\data\gtfs_raw           (nơi giải nén file zip)
DB_PATH = os.path.join(DATA_DIR, "stib_database.db")     # \BRUSSELS-BUS\data\stib_database.db   (nơi lưu database sau khi xây dựng)

# II. HÀM HỖ TRỢ GIẢI NÉN FILE ZIP TẢI VỀ

def unzip_files():
    if not os.path.exists(ZIP_PATH):
        raise FileNotFoundError(f"❌ Chưa có file zip tại {ZIP_PATH}")

    ## print("--- 1. Đang giải nén dữ liệu GTFS ---")
    os.makedirs(EXTRACT_DIR, exist_ok=True)              # Tạo thư mục giải nén nếu chưa có
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:      # Mở file zip, đặt tên là zip_ref
        zip_ref.extractall(EXTRACT_DIR)                  # Giải nén tất cả nội dung vào thư mục EXTRACT_DIR
    ## print("✅ Giải nén xong.")

# III. XÂY DỰNG DATABASE route_paths

def build_route_paths():
    unzip_files() 

    # --- BƯỚC 1: TẠO DATAFRAME TỪ CÁC FILE .txt LẤY CÁC TRƯỜNG DỮ LIỆU CẦN THIẾT TỪ CÁC DATAFRAME ---
    try:
        
        stops_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stops.txt"))             # Nạp bảng stops 
        routes_df = pd.read_csv(os.path.join(EXTRACT_DIR, "routes.txt"))           # Nạp bảng routes
        trips_df = pd.read_csv(os.path.join(EXTRACT_DIR, "trips.txt"))             # Nạp bảng trips
        stop_times_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stop_times.txt"))   # Nạp bảng stop_times



        stops_clean = stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]   # Chỉ lấy ID bến, tên bến và tọa độ
        routes_clean = routes_df[['route_id', 'route_short_name']]                 # Chỉ lấy ID tuyến và số hiệu xe (ví dụ: "71")
        trips_clean = trips_df[['route_id', 'trip_id', 'direction_id']]            # Lấy ID tuyến, ID chuyến và hướng đi (0: đi, 1: về)
        stop_times_clean = stop_times_df[['trip_id', 'stop_id', 'stop_sequence']]  # Lấy ID chuyến, ID bến và thứ tự dừng (1, 2, 3...)

    except Exception as e:
        print(f"Lỗi khi đọc file TXT: {e}")

    # --- BƯỚC 2: MERGE CÁC BẢNG LẠI VỚI NHAU tạo route_paths ---
    
    route_paths = (
    stop_times_clean                                                               # Bắt đầu từ bảng stop_times (bảng trung tâm chứa thứ tự bến)
    .merge(stops_clean, on='stop_id', how='inner')                                 # 1. Nối với stops để lấy Tên và Tọa độ (khớp qua stop_id)
    .merge(trips_clean, on='trip_id', how='inner')                                 # 2. Nối với trips để biết bến đó thuộc hướng nào (khớp qua trip_id)
    .merge(routes_clean, on='route_id', how='inner')                               # 3. Nối với routes để lấy số hiệu xe bus (khớp qua route_id)
    )

    # --- BƯỚC 3: LÀM SẠCH, TINH CHỈNH ---

    # a. Đổi tên cột cho giống với yêu cầu của bạn và hàm load_data
    route_paths = route_paths.rename(columns={
        'route_short_name': 'route_name',
        'direction_id': 'direction',
        'stop_sequence': 'stop_order'
    })
     
    # b. Lọc chỉ giữ lại các cột cần thiết cho hàm load_data
    cols = ['route_name', 'direction', 'stop_order', 'stop_id', 'stop_name', 'stop_lat', 'stop_lon']
    route_paths = route_paths[cols]

    # c. Loại bỏ trùng lặp 
    route_paths = route_paths.drop_duplicates(subset=['route_name', 'direction', 'stop_order'])

    # d. Sắp xếp theo trình tự bến xe Tên tuyến -> Hướng đi -> Thứ tự bến
    route_paths = route_paths.sort_values(['route_name', 'direction', 'stop_order'])

    # --- BƯỚC 4: LƯU route_paths VÀO DATABASE  ---

    try:
        conn = sqlite3.connect(DB_PATH)
        route_paths.to_sql("route_paths", conn, if_exists="replace", index=False)
        conn.close()
        print("✅ Hoàn tất! Database đã sẵn sàng.")

    except Exception as e:
        print(f"❌ Lỗi khi lưu Database: {e}")

build_route_paths()