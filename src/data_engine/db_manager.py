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

# III. XÂY DỰNG DATABASE route_paths VÀ CÁC BẢNG HÌNH HỌC

def build_route_paths():
    unzip_files() 

    # --- BƯỚC 1: TẠO DATAFRAME TỪ CÁC FILE .txt LẤY CÁC TRƯỜNG DỮ LIỆU CẦN THIẾT ---
    try:
        stops_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stops.txt"))             # Nạp bảng stops 
        routes_df = pd.read_csv(os.path.join(EXTRACT_DIR, "routes.txt"))           # Nạp bảng routes
        trips_df = pd.read_csv(os.path.join(EXTRACT_DIR, "trips.txt"))             # Nạp bảng trips
        stop_times_df = pd.read_csv(os.path.join(EXTRACT_DIR, "stop_times.txt"))   # Nạp bảng stop_times
        shapes_df = pd.read_csv(os.path.join(EXTRACT_DIR, "shapes.txt"))           # Nạp bảng shapes (Thêm mới để lấy tọa độ uốn lượn)

        stops_clean = stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]   # Chỉ lấy ID bến, tên bến và tọa độ
        routes_clean = routes_df[['route_id', 'route_short_name']]                 # Chỉ lấy ID tuyến và số hiệu xe (ví dụ: "71")
        trips_clean = trips_df[['route_id', 'trip_id', 'direction_id']]            # Lấy ID tuyến, ID chuyến và hướng đi (0: đi, 1: về)
        stop_times_clean = stop_times_df[['trip_id', 'stop_id', 'stop_sequence']]  # Lấy ID chuyến, ID bến và thứ tự dừng (1, 2, 3...)
        
        # Lọc dữ liệu hình học tuyến đường để lưu riêng phục vụ vẽ bản đồ (Thêm mới)
        shapes_clean = shapes_df[['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence']]
        trips_shapes = trips_df[['route_id', 'trip_id', 'shape_id']]

    except Exception as e:
        print(f"Lỗi khi đọc file TXT: {e}")

    # --- BƯỚC 2: MERGE CÁC BẢNG LẠI VỚI NHAU tạo route_paths ---
    route_paths = (
    stop_times_clean                                                               # Bắt đầu từ bảng stop_times
    .merge(stops_clean, on='stop_id', how='inner')                                 # 1. Nối với stops để lấy Tên và Tọa độ
    .merge(trips_clean, on='trip_id', how='inner')                                 # 2. Nối với trips để biết hướng đi
    .merge(routes_clean, on='route_id', how='inner')                               # 3. Nối với routes để lấy số hiệu xe bus
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

    # --- BƯỚC 4: LƯU CÁC BẢNG VÀO DATABASE ---
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 1. Lưu bảng route_paths gốc của bạn
        print("Đang lưu bảng route_paths...")
        route_paths.to_sql("route_paths", conn, if_exists="replace", index=False)
        
        # 2. Lưu bảng stops (Phục vụ hàm load_stops_table trong app.py)
        print("Đang lưu bảng stops...")
        stops_clean.to_sql("stops", conn, if_exists="replace", index=False)
        
        # 3. Lưu bảng hình học shapes và trips (Thêm mới phục vụ vẽ đường cong)
        print("Đang lưu bảng dữ liệu đường cong shapes...")
        shapes_clean.to_sql("shapes", conn, if_exists="replace", index=False)
        trips_shapes.to_sql("trips", conn, if_exists="replace", index=False)

        print("Đang lưu bảng routes để đối chiếu tên...")
        routes_clean.to_sql("routes", conn, if_exists="replace", index=False)
        
        # --- TẠO CÁC CHỈ MỤC (INDEX) ĐỂ APP TRA CỨU BẢN ĐỒ TỐC ĐỘ CAO (Cực kỳ quan trọng) ---
        print("Đang tối ưu hóa chỉ mục tốc độ cho cơ sở dữ liệu...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shape_id ON shapes(shape_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shape_seq ON shapes(shape_id, shape_pt_sequence)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_route ON trips(route_id)")
        
        conn.commit()
        conn.close()
        print("✅ Hoàn tất! Toàn bộ hệ thống cơ sở dữ liệu đường cong đã sẵn sàng.")

    except Exception as e:
        print(f"❌ Lỗi khi lưu Database: {e}")

# IV. HÀM HỖ TRỢ LẤY DATA FRAME route_paths TỪ DATABASE 

def get_dataframe_from_db(db_path):
    """Lấy DataFrame route_paths từ database thật"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Không tìm thấy file DB tại {db_path}")
    
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM route_paths"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Cho phép chạy độc lập file này từ terminal để đúc lại Database sạch
if __name__ == "__main__":
    build_route_paths()
