import streamlit as st
import folium
from streamlit_folium import st_folium
import sys
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN (Để import được src/logic) ---
project_root = Path(__file__).resolve().parents[2]
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

# Bây giờ có thể import logic của bạn
# from logic.router import a_star_search 

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="Brussels Bus Navigator", layout="wide")

st.title("🚌 Brussels Bus Real-time Navigator")

# Tạo Sidebar để nhập liệu
with st.sidebar:
    st.header("Tìm kiếm lộ trình")
    start_point = st.text_input("Điểm đi", placeholder="Nhập tọa độ hoặc trạm...")
    end_point = st.text_input("Điểm đến", placeholder="Nhập tọa độ hoặc trạm...")
    
    find_path = st.button("Tìm đường tối ưu")

# Tạo Layout chính
col1, col2 = st.columns([3, 1])

with col1:
    # Khởi tạo bản đồ Folium
    m = folium.Map(location=[50.8503, 4.3517], zoom_start=13)
    
    # Hiển thị bản đồ và bắt sự kiện Click
    map_data = st_folium(m, width="100%", height=600)

with col2:
    st.subheader("Thông tin chi tiết")
    if map_data["last_clicked"]:
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]
        st.success(f"📍 Tọa độ đã chọn:\n{lat:.5f}, {lng:.5f}")
        # Tại đây bạn có thể gọi hàm tìm trạm gần nhất
    else:
        st.info("Hãy click vào bản đồ để chọn vị trí.")