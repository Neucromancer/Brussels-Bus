import sys
import os
import sqlite3
import pandas as pd

# 1. Cấu hình Path để import từ src
current_dir = os.path.dirname(os.path.abspath(__file__)) # /Brussels Bus/tests
project_root = os.path.dirname(current_dir)              # /Brussels Bus
src_path = os.path.join(project_root, 'src')             # /Brussels Bus/src

if src_path not in sys.path:
    sys.path.insert(1, src_path)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import các hàm bạn đã viết
from logic.router import a_star_search
from logic.models import Stop, NextStopInfo
# Giả sử hàm load_data của bạn nằm trong logic/data_process.py
from data_engine.data_process import load_data 

# Giả định Coords đơn giản để truyền vào a_star_search
class Coords:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon

def get_data_from_db(db_path):
    """Lấy DataFrame route_paths từ database thật"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Không tìm thấy file DB tại {db_path}")
    
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM route_paths"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def run_real_test():
    print("--- 🚀 KHỞI ĐỘNG KIỂM TRA LOGIC VỚI DỮ LIỆU THẬT ---")

    # BƯỚC 1: Lấy dữ liệu từ DB
    db_path = os.path.join(project_root, "data", "stib_database.db")
    print(f"-> Đang đọc database từ: {db_path}")
    route_path_df = get_data_from_db(db_path)

    # BƯỚC 2: Chuyển đổi DataFrame thành List các đối tượng Stop (Hàm bạn đã viết)
    print(f"-> Đang xử lý {len(route_path_df)} dòng dữ liệu thành mạng lưới Graph...")
    all_stops_list = load_data(route_path_df) 
    print(f"✅ Đã khởi tạo thành công {len(all_stops_list)} bến xe.")

    # BƯỚC 3: Thiết lập điểm xuất phát và đích (Tọa độ thật tại Brussels)
    # Ví dụ: Từ gần bến Delta đến gần bến Flagey
    user_pos = Coords(50.837226, 4.300408)  # Gần Delta
    dest_pos = Coords(50.854424, 4.438357)  # Gần Flagey

    print(f"-> Đang tìm đường đi tối ưu bằng A*...")
    
    # BƯỚC 4: Gọi thuật toán A*
    results = a_star_search(user_pos, dest_pos, all_stops_list)

        # BƯỚC 5: Hiển thị kết quả
    if results:
        top_results = results[:100]
        
        print("\n" + "="*80)
        print(f"📋 DANH SÁCH {len(top_results)} KẾT QUẢ NHANH NHẤT")
        print("="*80)
        
        for i, res in enumerate(top_results, 1):
            print(f"Top {i:2}: {res['duration']:.2f} phút")
        
        print("="*80)
        
        # === CHI TIẾT KẾT QUẢ TỐT NHẤT ===
        best = results[0]
        path_nodes = best['path']
        
        print(f"\n🏆 CHI TIẾT KẾT QUẢ TỐT NHẤT")
        print(f"⏱️ Tổng thời gian: {best['duration']:.2f} phút")
        print(f"{'TÊN BẾN':<30} | {'VỊ TRÍ (LAT, LON)':<25} | {'CHUYẾN'}")
        print("-" * 80)

        route_data = []

        for idx, node in enumerate(path_nodes):
            stop = node.stop

            route_data.append([stop.lat, stop.lon, stop.name])
            
            # 1. Định dạng thông tin cơ bản
            stop_display = f"[{stop.id}] {stop.name}"
            coords_display = f"({stop.lat:.4f}, {stop.lon:.4f})"
            route_display = f"{node.route_id}" if node.route_id else "---"
            
            # 2. Xử lý thời gian (node.g là tổng phút đã đi từ đầu)
            time_display = f"{node.g:>5.2f} phút"
            
            # 3. Tính toán thời gian chặng (thời gian đi từ bến trước đến bến này)
            if idx > 0:
                segment_time = node.g - path_nodes[idx-1].g
                time_display += f" (+{segment_time:.1f}m)"

            # 4. Ký hiệu biểu tượng
            if idx == 0:
                icon = "🏁 "
            elif idx == len(path_nodes) - 1:
                icon = "🚩 "
            else:
                icon = "┣━ "

            # 5. In dòng dữ liệu căn lề thẳng hàng
            print(f"{icon}{stop_display:<27} | {coords_display:<25} | {route_display:<12} | {time_display}")

        # In thêm chặng đi bộ cuối cùng nếu có (từ bến cuối về tọa độ đích thực tế)
        final_walk = best['duration'] - path_nodes[-1].g
        if final_walk > 0.1: # Chỉ in nếu đi bộ đáng kể
            print(f"🚶 {'Đi bộ về điểm đích':<27} | {'---':<25} | {'---':<12} | {best['duration']:>5.2f} phút (+{final_walk:.1f}m)")

        return route_data

    else:
        print("❌ Không tìm thấy lộ trình nào phù hợp.")
if __name__ == "__main__":
    run_real_test()