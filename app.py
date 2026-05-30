import sys
import pandas as pd
import streamlit as st
from pathlib import Path

# --- 1. CẤU HÌNH ĐƯỜNG DẪN PROJECT ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
for path in (BASE_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# --- 2. IMPORT MODULE ---
from UI.auth import login_form
from data_engine.data_process import (
    resolve_db_path, load_stops_table, load_route_objects, 
    make_stop_lookup, build_route_segments, build_selected_route_rows
)
from logic.router import a_star_search
from UI.state import init_state, clear_route_result, set_start_coords, set_goal_coords, set_route_results, reset_all
from UI.map_builder import get_current_coords, nearest_stop_id, build_route_map, render_map, collect_route_rows, format_route_rank_text
from UI.admin_panel import render_admin_panel

# --- 3. KHỞI TẠO APP ---
st.set_page_config(page_title="Tìm đường đi tàu điện / bus", page_icon="🚌", layout="wide")
init_state()
st.title("🚌 Ứng dụng tìm đường đi tàu điện / bus")

# --- 4. TẢI DỮ LIỆU ---
db_path = resolve_db_path()
route_paths_raw = None

with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        if "disabled_routes" not in st.session_state: st.session_state.disabled_routes = set()
        disabled_routes_tuple = tuple(sorted(list(st.session_state.get("disabled_routes", set()))))
        
        route_paths_raw, _, _ = load_route_objects(str(db_path), disabled_routes=())
        route_paths, all_stops, coordinates = load_route_objects(str(db_path), disabled_routes=disabled_routes_tuple)
        stop_lookup = make_stop_lookup(str(db_path), disabled_routes=disabled_routes_tuple)
        stops_df_filtered = load_stops_table(str(db_path), disabled_routes=disabled_routes_tuple)
        
        active_stop_ids = {str(stop.id) for stop in all_stops}
        stops_df = stops_df_filtered[stops_df_filtered['stop_id'].astype(str).isin(active_stop_ids)]
    except Exception as exc:
        st.error(f"Lỗi Database: {exc}"); st.stop()

# =====================================================================
# 5. BỐ CỤC GIAO DIỆN CHÍNH (BẢN ĐỒ & ĐIỀU KHIỂN)
# =====================================================================
# Chia màn hình: Bản đồ chiếm 70% bên trái, Điều khiển chiếm 30% bên phải
col_map, col_ctrl = st.columns([7, 3], gap="large")

# -----------------------------------------------------------
# CỘT BÊN PHẢI: BẢNG ĐIỀU KHIỂN (Xử lý logic trước để lấy tọa độ)
# -----------------------------------------------------------
with col_ctrl:
    st.subheader("⚙️ Bảng Điều Khiển")
    
    # 1. Xem trước các bến của một tuyến
    route_options = ["— Không chọn —"] + sorted([str(r) for r in route_paths["route_name"].dropna().astype(str).unique()])
    default_route_idx = route_options.index(st.session_state.selected_route_name) if st.session_state.get("selected_route_name") in route_options else 0
    selected_route_name = st.selectbox("Hiển thị toàn bộ bến của tuyến:", route_options, index=default_route_idx, key="selected_route_selector")
    selected_route_name = None if selected_route_name == "— Không chọn —" else selected_route_name

    if st.session_state.get("selected_route_name") != selected_route_name:
        st.session_state.selected_route_name = selected_route_name
    selected_route_rows = build_selected_route_rows(route_paths, selected_route_name)

    st.write("---")
    
    # 2. Phương thức chọn điểm
    input_mode = st.radio("Cách chọn điểm:", ["Ghim trên bản đồ", "Chọn bến có sẵn"], horizontal=True, key="input_mode_radio")
    if st.session_state.active_input_mode is not None and st.session_state.active_input_mode != input_mode:
        clear_route_result()
    st.session_state.active_input_mode = input_mode

    # Tính toán tọa độ hiện tại
    start_coords, goal_coords, start_label, goal_label = get_current_coords(input_mode, stop_lookup)
    nearest_start_stop = nearest_stop_id(start_coords.lat, start_coords.lon, coordinates) if start_coords else None
    nearest_goal_stop = nearest_stop_id(goal_coords.lat, goal_coords.lon, coordinates) if goal_coords else None

    # 3. Các nút điều khiển
    if input_mode == "Ghim trên bản đồ":
        st.info(f"Đang chờ click: **{'📍 Đặt điểm đi' if st.session_state.pin_mode == 'start' else '🚩 Đặt điểm đến'}**")
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("📍 Điểm đi", use_container_width=True): st.session_state.pin_mode = "start"; st.rerun()
        with c2: 
            if st.button("🚩 Điểm đến", use_container_width=True): st.session_state.pin_mode = "goal"; st.rerun()
        if st.button("🗑️ Xóa điểm ghim", use_container_width=True): reset_all()
    else:
        options = [f"{row.stop_name}  ·  {row.stop_id}" for row in stops_df.itertuples(index=False)]
        choice_start = st.selectbox("📍 Bến xuất phát", options, index=0, key="manual_start_selector")
        if st.session_state.manual_start_id != (chosen_start_id := choice_start.split("·")[-1].strip()):
            st.session_state.manual_start_id = chosen_start_id; clear_route_result()
            
        choice_goal = st.selectbox("🚩 Bến đích", options, index=min(1, len(options) - 1), key="manual_goal_selector")
        if st.session_state.manual_goal_id != (chosen_goal_id := choice_goal.split("·")[-1].strip()):
            st.session_state.manual_goal_id = chosen_goal_id; clear_route_result()
            
        if st.button("🗑️ Xóa lựa chọn", use_container_width=True): reset_all()

    st.write("---")
    
    # 4. Tóm tắt tọa độ đã chọn
    if start_coords: st.success(f"**📍 Xuất phát:**\n\n{start_label or f'{start_coords.lat:.6f}, {start_coords.lon:.6f}'}")
    else: st.warning("Chưa chọn điểm xuất phát.")
    
    if goal_coords: st.success(f"**🚩 Đích đến:**\n\n{goal_label or f'{goal_coords.lat:.6f}, {goal_coords.lon:.6f}'}")
    else: st.warning("Chưa chọn đích đến.")

    st.write("---")
    
    # 5. Nút tìm đường
    if st.button("TÌM ĐƯỜNG ĐI", type="primary", use_container_width=True):
        if not start_coords or not goal_coords:
            st.error("⚠️ Vui lòng chọn đủ 2 điểm!")
        else:
            with st.spinner("Đang chạy thuật toán A*..."):
                results = a_star_search(start_coords, goal_coords, all_stops)
                if results: 
                    set_route_results(results)
                    st.rerun() # Refresh màn hình để vẽ map ngay lập tức
                else: 
                    st.warning("❌ Không tìm thấy đường!"); clear_route_result()

# -----------------------------------------------------------
# CỘT BÊN TRÁI: KHU VỰC BẢN ĐỒ VÀ KẾT QUẢ
# -----------------------------------------------------------
with col_map:
    st.subheader("🗺️ Bản đồ tương tác")
    
    # Nút radio hiển thị lộ trình nằm ngay trên bản đồ
    route_results = st.session_state.get("route_results", [])
    if route_results:
        options = [f"Phương án {i+1} ({res['duration']:.1f} phút)" for i, res in enumerate(route_results)]
        options[0] = options[0].replace("Phương án 1", "⭐ Phương án 1 (Nhanh nhất)")

        current_idx = st.session_state.get("selected_solution_idx", 0)
        selected_option = st.radio("Lựa chọn lộ trình hiển thị:", options, index=current_idx, horizontal=True)
        selected_idx = options.index(selected_option)

        if selected_idx != current_idx:
            st.session_state.selected_solution_idx = selected_idx
            st.session_state.route_result = route_results[selected_idx]
            st.rerun()

    # Dựng và Render bản đồ
    map_obj = build_route_map(
        all_stops, stop_lookup, 
        path_nodes=st.session_state.route_result["path"] if st.session_state.route_result else None, 
        start_coords=start_coords, goal_coords=goal_coords, 
        start_nearest_stop=nearest_start_stop, goal_nearest_stop=nearest_goal_stop, 
        selected_route_rows=selected_route_rows
    )
    map_state = render_map(map_obj)

    # Xử lý sự kiện click trên bản đồ
    if input_mode == "Ghim trên bản đồ" and (clicked := (map_state or {}).get("last_clicked")):
        click_key = (round(float(clicked["lat"]), 6), round(float(clicked["lng"]), 6))
        if st.session_state.last_processed_click != click_key:
            st.session_state.last_processed_click = click_key
            nearest = nearest_stop_id(float(clicked["lat"]), float(clicked["lng"]), coordinates)
            if st.session_state.pin_mode == "start": set_start_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
            else: set_goal_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
            st.rerun()


# =====================================================================
# 6. CHI TIẾT LỘ TRÌNH ĐANG CHỌN (NẰM BÊN DƯỚI BẢN ĐỒ)
# =====================================================================
active_result = st.session_state.get("route_result")

if active_result:
    st.write("---")
    st.subheader("📄 Chi tiết lộ trình")
    
    path_nodes = active_result["path"]
    duration = active_result["duration"]
    current_idx = st.session_state.get("selected_solution_idx", 0)
    
    st.success(f"⭐ Đang xem {format_route_rank_text(current_idx + 1)}. Lộ trình đi qua {len(path_nodes)} bến, tổng thời gian ước tính: **{duration:.2f} phút**.")
    
    # === BỔ SUNG: BẢNG CHỈ SỐ HIỆU SUẤT THUẬT TOÁN A* ===
    st.write("**📊 Hiệu suất Thuật toán A***")
    metric_cols = st.columns(4)
    metric_cols[0].metric("⏱️ Thời gian chạy", f"{active_result.get('execution_time', 0):.4f} s")
    metric_cols[1].metric("📥 Node vào hàng đợi", f"{active_result.get('nodes_enqueued', 0):,}")
    metric_cols[2].metric("🔍 Node đã duyệt (Pop)", f"{active_result.get('nodes_visited', 0):,}")
    metric_cols[3].metric("🛤️ Độ dài đường đi", f"{len(path_nodes)} bến")
    st.write("")
    # ====================================================

    route_segments = build_route_segments(path_nodes)
    if not route_segments.empty:
        st.write("**🚌 Các chặng phương tiện công cộng**")
        st.dataframe(route_segments, use_container_width=True, hide_index=True)
        st.info("  •  ".join(f"Tuyến {row['Tuyến']} ({row['Từ']} → {row['Đến']})" for _, row in route_segments.iterrows()))
        
    path_rows = collect_route_rows(path_nodes, stop_lookup)
    if path_rows:
        with st.expander("📍 Danh sách chi tiết từng bến đi qua", expanded=True):
            st.dataframe(pd.DataFrame(path_rows), use_container_width=True, hide_index=True)

    final_walk_minutes = duration - float(path_nodes[-1].g)
    if final_walk_minutes > 0.1:
        st.caption(f"🚶 Cần khoảng {final_walk_minutes:.1f} phút đi bộ từ bến cuối tới điểm đến.")
        
st.divider()

# =====================================================================
# 7. THÔNG TIN DỮ LIỆU BẢN ĐỒ (Database Info)
# =====================================================================
with st.expander("🗄️ Thông tin Dữ liệu Mạng lưới (Database)", expanded=False):
    info_cols = st.columns(3)
    info_cols[0].metric("Tổng số Bến (Stops)", f"{len(stop_lookup):,}")
    info_cols[1].metric("Không gian trạng thái (Total Nodes)", f"{len(all_stops):,}")
    info_cols[2].metric("Số cạnh kết nối (Route Paths)", f"{len(route_paths):,}")
    st.caption(f"**Nguồn CSDL:** `{db_path}`")
    st.caption("*Bạn có thể so sánh Không gian trạng thái tổng này với **Số Node đã duyệt** ở phần Kết quả để thấy khả năng tỉa nhánh (pruning) và sức mạnh của hàm Heuristic trong thuật toán A*.*")

# =====================================================================
# 8. ADMIN PANEL
# =====================================================================
login_form()
render_admin_panel(route_paths_raw, route_paths)