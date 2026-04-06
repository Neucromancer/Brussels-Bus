import os
import sys

# Cấu hình đường dẫn để nhận diện thư mục src và core
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(current_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Import hàm của Nhóm 1
from core.data_loader import load_stop_times, load_coordinates_for_used_stops

def run_integration_test():
    # Trỏ đến file database bạn vừa tạo ra
    db_path = os.path.join(base_dir, "data", "stib_database.db")
    
    print("1. Thử nghiệm hàm load_stop_times() của Nhóm 1...")
    stop_times = load_stop_times(db_path)
    print(f"✅ Thành công! Đã lấy ra {len(stop_times)} dòng lịch trình.")
    
    print("\n2. Thử nghiệm hàm load_coordinates() của Nhóm 1...")
    # Lấy thử tọa độ của 100 bến đầu tiên để test cho nhanh
    coords = load_coordinates_for_used_stops(db_path, stop_times[:100])
    print(f"✅ Thành công! Đã lấy ra tọa độ của {len(coords)} bến.")
    
    print("\n🎉 Tích hợp Data và Logic thành công mĩ mãn!")

if __name__ == "__main__":
    run_integration_test()