import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from tests.test_logic import run_real_test
import folium

# 1. Danh sách tọa độ mẫu (Bạn hãy thay thế bằng tọa độ thực tế từ thuật toán của bạn)
# Cấu trúc: [Lat, Lon, "Tên trạm"]
route_data = [
    [50.8203, 4.4014, "GINETTE JAVAUX"],
    [50.8190, 4.3985, "DELTA"],
    [50.8175, 4.4005, "CHIREC"],
    [50.8188, 4.3910, "FRAITEUR"],
    [50.8205, 4.3840, "CIM. D'IXELLES"],
    [50.8168, 4.3815, "ULB"],
    [50.8185, 4.3795, "JEANNE"],
    [50.8175, 4.3780, "BUYL"],
    [50.8185, 4.3770, "GEO BERNIER"],
    [50.8240, 4.3740, "ETANGS D'IXELLES"],
    [50.8275, 4.3735, "FLAGEY"]
]

route_data = run_real_test() # Lấy dữ liệu thực tế từ thuật toán A*

# 2. Khởi tạo bản đồ tại trung tâm Brussels
# 50.8503, 4.3517 là tọa độ trung tâm thành phố
m = folium.Map(location=[50.83, 4.37], zoom_start=13, tiles="OpenStreetMap")

# 3. Lấy danh sách tọa độ thuần túy để vẽ đường nối (PolyLine)
path_coords = [[point[0], point[1]] for point in route_data]

# 4. Vẽ đường nối giữa các trạm (Màu xanh đậm để dễ nhìn)
folium.PolyLine(
    locations=path_coords,
    color="#2c3e50",
    weight=5,
    opacity=0.8,
    tooltip="Lộ trình A*"
).add_to(m)

# 5. Thêm các Marker (điểm ghim) cho từng trạm
for lat, lon, name in route_data:
    folium.CircleMarker(
        location=[lat, lon],
        radius=6,
        popup=name,
        color="#e74c3c",
        fill=True,
        fill_color="#e74c3c",
        fill_opacity=0.9
    ).add_to(m)

# 6. Lưu bản đồ ra file HTML và tự động mở (nếu dùng local)
m.save("brussels_route.html")

print("Đã tạo file 'brussels_route.html'. Hãy mở file này bằng trình duyệt để xem kết quả!")