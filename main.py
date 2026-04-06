import os
import sys
import sqlite3

def get_stop_names(db_path, stop_ids):
    """Truy vấn database để dịch ID sang tên bến xe thực tế"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Ép kiểu tất cả ID về string để tránh lỗi mismatch kiểu dữ liệu
    stop_ids_str = [str(sid) for sid in stop_ids]
    
    # Tạo chuỗi ?, ?, ? cho câu query SQL
    placeholders = ",".join(["?"] * len(stop_ids_str))
    query = f"SELECT stop_id, stop_name FROM stops WHERE stop_id IN ({placeholders})"
    
    cur.execute(query, stop_ids_str)
    rows = cur.fetchall()
    conn.close()
    
    # Trả về một bộ từ điển (Dictionary) dạng: { '5001': 'Atomium', '5010': 'Grand Place' }
    return {str(row[0]): row[1] for row in rows}

# --- CẤU HÌNH ĐƯỜNG DẪN ---
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "data", "stib_database.db")

# --- IMPORT MODULES ---
from core.data_loader import load_stop_times, load_coordinates_for_used_stops
from core.graph_builder import build_graph
from core.a_star import a_star
from utils.nearest_stop import NearestStopFinder

def main():
    print("="*60)
    print("🚇 HỆ THỐNG TÌM ĐƯỜNG BRUSSELS BUS / SUBWAY (A* ALGORITHM) 🚇")
    print("="*60)

    # 1. TẢI DỮ LIỆU
    print("\n[1/3] Đang nạp cơ sở dữ liệu và xây dựng đồ thị...")
    if not os.path.exists(db_path):
        print("❌ Lỗi: Không tìm thấy database! Hãy chạy: python src/data_engine/db_manager.py")
        sys.exit(1)

    stop_times = load_stop_times(db_path)
    coordinates = load_coordinates_for_used_stops(db_path, stop_times)
    graph = build_graph(stop_times)
    print(f"✅ Đã tải xong {len(coordinates)} bến xe và kết nối đồ thị.")

    # 2. KHỞI TẠO CÔNG CỤ TÌM BẾN XE
    # Lấy danh sách ID hợp lệ để khởi tạo KDTree
    valid_ids = list(coordinates.keys())
    stop_finder = NearestStopFinder(db_path, valid_stop_ids=valid_ids)

    # 3. NHẬP LIỆU
    print("\n" + "-"*60)
    print("📍 Vui lòng nhập thông tin di chuyển (hoặc Enter để dùng mặc định):")
    print("   (Mặc định: Đi từ Atomium -> Quảng trường Grand Place)")
    
    try:
        lat1_input = input("Vĩ độ (Lat) điểm BẮT ĐẦU: ").strip()
        start_lat = float(lat1_input) if lat1_input else 50.8949
        
        lon1_input = input("Kinh độ (Lon) điểm BẮT ĐẦU: ").strip()
        start_lon = float(lon1_input) if lon1_input else 4.3415

        lat2_input = input("Vĩ độ (Lat) điểm ĐẾN: ").strip()
        end_lat = float(lat2_input) if lat2_input else 50.8467
        
        lon2_input = input("Kinh độ (Lon) điểm ĐẾN: ").strip()
        end_lon = float(lon2_input) if lon2_input else 4.3528
        
        time_input = input("Thời gian xuất phát (HH:MM:SS) [Mặc định 08:00:00]: ").strip()
        start_time = time_input if time_input else "08:00:00"

    except ValueError:
        print("❌ Lỗi: Tọa độ phải là số thực! Vui lòng chạy lại.")
        sys.exit(1)

    # 4. TÌM BẾN GẦN NHẤT
    print("\n[2/3] Đang định vị bến xe gần nhất...")
    start_id = stop_finder.find(start_lat, start_lon)
    end_id = stop_finder.find(end_lat, end_lon)
    
    print(f"✅ Đã tìm thấy: Bắt đầu tại bến [ID: {start_id}] -> Kết thúc tại bến [ID: {end_id}]")

    # 5. CHẠY THUẬT TOÁN AI
    print(f"\n[3/3] Đang tìm đường đi tối ưu lúc {start_time} bằng thuật toán A*...")
    path = a_star(graph, start_id, end_id, coordinates, start_time)

    # 6. IN KẾT QUẢ ĐÃ ĐƯỢC LÀM ĐẸP VÀ PHÂN BIỆT RÕ RÀNG
    print("\n" + "="*60)
    if path:
        print("🎉 TÌM THẤY LỘ TRÌNH THÀNH CÔNG!")
        print(f"Tổng số điểm dừng/chuyển bến: {len(path)} điểm.")
        print("\n👉 CHI TIẾT TUYẾN ĐƯỜNG:")
        
        # Gọi hàm dịch ID sang tên
        name_map = get_stop_names(db_path, path)
        
        # In từng bước một cách trực quan
        for i, stop_id in enumerate(path):
            # Lấy tên bến
            stop_name = name_map.get(str(stop_id), "Không xác định")
            
            # Kết hợp Tên và ID để tạo sự phân biệt độc nhất
            display_text = f"{stop_name} [ID: {stop_id}]"
            
            if i == 0:
                print(f"🟢 BẮT ĐẦU : {display_text}")
            elif i == len(path) - 1:
                print(f"   |")
                print(f"🔴 KẾT THÚC : {display_text}")
            else:
                print(f"   |")
                # Kiểm tra: Nếu tên bến này GIỐNG HỆT bến ngay trước nó
                prev_stop_name = name_map.get(str(path[i-1]), "")
                if stop_name == prev_stop_name:
                    print(f"   🚶 (Đi bộ chuyển tuyến) -> {display_text}")
                else:
                    print(f"   ↓ (Đi qua: {display_text})")
                
    else:
        print("❌ Rất tiếc, không tìm thấy đường đi nào nối giữa 2 vị trí này vào thời gian trên.")
    print("="*60)

if __name__ == "__main__":
    main()