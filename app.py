import os
import sys
from dataclasses import dataclass
from datetime import datetime

import streamlit as st
import folium
import streamlit.components.v1 as components

try:
    from streamlit_folium import st_folium
except Exception:
    st_folium = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
for path in (BASE_DIR, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.data_engine.data_access import load_network_data
from src.logic.router import a_star_search
from src.logic.route_utils import (
    build_route_map,
    build_selection_map,
    nearest_stop_id,
    route_segment_table,
    route_step_table,
    route_text,
)

DB_PATH = os.path.join(BASE_DIR, "src", "data_engine", "stib_database.db")
DEFAULT_START_LAT = 50.8466
DEFAULT_START_LON = 4.3528
DEFAULT_GOAL_LAT = 50.8456
DEFAULT_GOAL_LON = 4.3572


@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float


def render_map(map_obj, key: str):
    if st_folium is not None:
        return st_folium(map_obj, key=key, height=640, width=None)

    components.html(map_obj.get_root().render(), height=640, scrolling=False)
    return {}


st.set_page_config(
    page_title="Tìm đường đi tàu điện / bus",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 Ứng dụng tìm đường đi tàu điện / bus")

@st.cache_data(show_spinner=False)
def load_all_data(db_path: str):
    return load_network_data(db_path)


with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        route_paths, stops_df, all_stops, coordinates, stop_lookup = load_all_data(DB_PATH)
    except Exception as exc:
        st.error(f"Không thể nạp dữ liệu từ database: {exc}")
        st.stop()

if "start_coords" not in st.session_state:
    st.session_state.start_coords = Coords(DEFAULT_START_LAT, DEFAULT_START_LON)
if "goal_coords" not in st.session_state:
    st.session_state.goal_coords = Coords(DEFAULT_GOAL_LAT, DEFAULT_GOAL_LON)
if "start_id" not in st.session_state:
    st.session_state.start_id = nearest_stop_id(
        st.session_state.start_coords.lat, st.session_state.start_coords.lon, coordinates
    )
if "goal_id" not in st.session_state:
    st.session_state.goal_id = nearest_stop_id(
        st.session_state.goal_coords.lat, st.session_state.goal_coords.lon, coordinates
    )
if "results" not in st.session_state:
    st.session_state.results = None
if "searched" not in st.session_state:
    st.session_state.searched = False
if "input_mode" not in st.session_state:
    st.session_state.input_mode = "Ghim vị trí"
if "pin_target" not in st.session_state:
    st.session_state.pin_target = "Điểm đi"
if "last_processed_click" not in st.session_state:
    st.session_state.last_processed_click = None

# Map đầu trang luôn là một vùng duy nhất:
# - trước khi bấm tìm: hiển thị điểm đi/đến
# - sau khi tìm xong: hiển thị lộ trình ngay trên chính vùng đó
if st.session_state.searched and st.session_state.results:
    best = st.session_state.results[0]
    top_map = build_route_map(
        best["path"],
        stop_lookup,
        st.session_state.start_coords,
        st.session_state.goal_coords,
        start_id=str(st.session_state.start_id or ""),
        goal_id=str(st.session_state.goal_id or ""),
    )
else:
    top_map = build_selection_map(st.session_state.start_coords, st.session_state.goal_coords)

st.subheader("Bản đồ")
if top_map is not None:
    map_state = render_map(top_map, key="route-map" if st.session_state.searched else "selection-map")
    if not st.session_state.searched and st_folium is not None:
        clicked = map_state.get("last_clicked") if isinstance(map_state, dict) else None
        if clicked and st.session_state.input_mode == "Ghim vị trí":
            lat = round(float(clicked["lat"]), 6)
            lon = round(float(clicked["lng"]), 6)
            click_key = (st.session_state.pin_target, lat, lon)
            if click_key != st.session_state.last_processed_click:
                st.session_state.last_processed_click = click_key
                if st.session_state.pin_target == "Điểm đi":
                    st.session_state.start_coords = Coords(lat, lon)
                    st.session_state.start_id = nearest_stop_id(lat, lon, coordinates)
                else:
                    st.session_state.goal_coords = Coords(lat, lon)
                    st.session_state.goal_id = nearest_stop_id(lat, lon, coordinates)
                st.rerun()
else:
    st.info("Chưa có điểm ghim để hiển thị bản đồ.")

if st_folium is None:
    st.warning(
        "Môi trường hiện tại chưa có `streamlit_folium`, nên thao tác ghim trực tiếp trên bản đồ có thể không hoạt động. "
        "Khi đó hãy dùng các ô tọa độ bên dưới."
    )

st.subheader("Chọn điểm")
st.session_state.input_mode = st.radio(
    "Cách nhập",
    ["Ghim vị trí", "Chọn bến có sẵn"],
    horizontal=True,
    index=0 if st.session_state.input_mode == "Ghim vị trí" else 1,
)

start_time = st.time_input(
    "Giờ xuất phát",
    value=datetime.now().time().replace(second=0, microsecond=0),
)
start_time_str = start_time.strftime("%H:%M:%S")

if st.session_state.input_mode == "Ghim vị trí":
    st.session_state.pin_target = st.radio(
        "Đang ghim cho",
        ["Điểm đi", "Điểm đến"],
        horizontal=True,
        index=0 if st.session_state.pin_target == "Điểm đi" else 1,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Điểm đi**")
        start_lat = float(
            st.number_input(
                "Vĩ độ xuất phát",
                value=float(st.session_state.start_coords.lat),
                format="%.6f",
            )
        )
        start_lon = float(
            st.number_input(
                "Kinh độ xuất phát",
                value=float(st.session_state.start_coords.lon),
                format="%.6f",
            )
        )
    with right:
        st.markdown("**Điểm đến**")
        goal_lat = float(
            st.number_input(
                "Vĩ độ điểm đến",
                value=float(st.session_state.goal_coords.lat),
                format="%.6f",
            )
        )
        goal_lon = float(
            st.number_input(
                "Kinh độ điểm đến",
                value=float(st.session_state.goal_coords.lon),
                format="%.6f",
            )
        )

    st.session_state.start_coords = Coords(start_lat, start_lon)
    st.session_state.goal_coords = Coords(goal_lat, goal_lon)
    st.session_state.start_id = nearest_stop_id(start_lat, start_lon, coordinates)
    st.session_state.goal_id = nearest_stop_id(goal_lat, goal_lon, coordinates)

    help_col1, help_col2 = st.columns(2)
    with help_col1:
        if st.session_state.start_id and st.session_state.start_id in stop_lookup:
            st.info(
                f"Bến gần nhất cho điểm đi: **{stop_lookup[st.session_state.start_id]['stop_name']}** "
                f"(ID: `{st.session_state.start_id}`)"
            )
        else:
            st.warning("Không tìm được bến gần nhất cho điểm đi.")
    with help_col2:
        if st.session_state.goal_id and st.session_state.goal_id in stop_lookup:
            st.info(
                f"Bến gần nhất cho điểm đến: **{stop_lookup[st.session_state.goal_id]['stop_name']}** "
                f"(ID: `{st.session_state.goal_id}`)"
            )
        else:
            st.warning("Không tìm được bến gần nhất cho điểm đến.")
else:
    options = [f"{row.stop_name}  ·  {row.stop_id}" for row in stops_df.itertuples(index=False)]
    choice_start = st.selectbox("Bến xuất phát", options, index=0)
    choice_goal = st.selectbox("Bến đích", options, index=min(1, len(options) - 1))
    st.session_state.start_id = choice_start.split("·")[-1].strip()
    st.session_state.goal_id = choice_goal.split("·")[-1].strip()

    start_info = stop_lookup.get(st.session_state.start_id)
    goal_info = stop_lookup.get(st.session_state.goal_id)
    if start_info:
        st.session_state.start_coords = Coords(float(start_info["stop_lat"]), float(start_info["stop_lon"]))
        st.info(f"Xuất phát: **{start_info['stop_name']}** (ID: `{st.session_state.start_id}`)")
    if goal_info:
        st.session_state.goal_coords = Coords(float(goal_info["stop_lat"]), float(goal_info["stop_lon"]))
        st.info(f"Điểm đến: **{goal_info['stop_name']}** (ID: `{st.session_state.goal_id}`)")

run = st.button("Tìm đường đi", type="primary", use_container_width=True)

if run:
    if st.session_state.start_coords is None or st.session_state.goal_coords is None:
        st.error("Không thể xác định bến xuất phát hoặc bến đích.")
        st.stop()

    with st.spinner("Đang chạy thuật toán A*..."):
        try:
            results = a_star_search(
                Coords(float(st.session_state.start_coords.lat), float(st.session_state.start_coords.lon)),
                Coords(float(st.session_state.goal_coords.lat), float(st.session_state.goal_coords.lon)),
                all_stops,
            )
            st.session_state.results = results
            st.session_state.searched = True
        except Exception as exc:
            st.error(f"Lỗi khi chạy tìm đường đi: {exc}")
            st.stop()

if st.session_state.searched:
    results = st.session_state.results or []
    if not results:
        st.warning("Không tìm được đường đi phù hợp từ dữ liệu hiện tại.")
    else:
        best = results[0]
        path_nodes = best["path"]

        st.success(
            f"Tìm thấy đường đi với {len(path_nodes)} bến. Tổng thời gian ước tính: {best['duration']:.2f} phút."
        )

        route_text_value = route_text(path_nodes, stop_lookup)
        if route_text_value:
            st.text_area("Lộ trình có tuyến xe", route_text_value, height=120)
        else:
            st.info("Không trích xuất được tên bến từ lộ trình này.")

        st.markdown("**Bảng từng chặng**")
        step_df = route_step_table(path_nodes, stop_lookup)
        st.dataframe(step_df, use_container_width=True, hide_index=True)

        segment_df = route_segment_table(path_nodes, stop_lookup)
        if not segment_df.empty:
            with st.expander("Xem các tuyến xe đã đi"):
                st.dataframe(segment_df, use_container_width=True, hide_index=True)

with st.expander("Thông tin dữ liệu", expanded=False):
    st.metric("Số bến", f"{len(stop_lookup):,}")
    st.metric("Số node graph", f"{len(all_stops):,}")
    st.metric("Số dòng route_paths", f"{len(route_paths):,}")
    st.write("**Database**")
    st.code(DB_PATH)
    st.write("**Giờ xuất phát**")
    st.code(start_time_str)
