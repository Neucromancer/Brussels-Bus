import os
import sys
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# Make the project importable when running: streamlit run app.py
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Existing project modules
from core.data_loader import load_stop_times, load_coordinates_for_used_stops
from core.graph_builder import build_graph
from core.a_star import a_star
from utils.time_utils import time_to_seconds


DB_PATH = os.path.join(BASE_DIR, "src", "data_engine", "stib_database.db")
DEFAULT_START_LAT = 50.8466
DEFAULT_START_LON = 4.3528
DEFAULT_GOAL_LAT = 50.8456
DEFAULT_GOAL_LON = 4.3572


# -----------------------------------------------------------------------------
# Data loading helpers
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_stops_table(db_path: str) -> pd.DataFrame:
    """Load stop metadata for labels / dropdowns."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops",
            conn,
        )
    finally:
        conn.close()

    df["stop_id"] = df["stop_id"].astype(str)
    return df.drop_duplicates(subset=["stop_id"]).sort_values(["stop_name", "stop_id"])


@st.cache_data(show_spinner=False)
def load_route_objects(db_path: str):
    """Load A* graph, coordinates and raw stop_times from the SQLite database."""
    stop_times = load_stop_times(db_path)
    graph = build_graph(stop_times)
    coordinates = load_coordinates_for_used_stops(db_path, stop_times)
    return stop_times, graph, coordinates


@st.cache_data(show_spinner=False)
def make_stop_lookup(db_path: str) -> Dict[str, Dict[str, object]]:
    df = load_stops_table(db_path)
    return {
        row.stop_id: {
            "stop_name": row.stop_name,
            "stop_lat": float(row.stop_lat),
            "stop_lon": float(row.stop_lon),
        }
        for row in df.itertuples(index=False)
    }


# -----------------------------------------------------------------------------
# Routing helpers
# -----------------------------------------------------------------------------
def nearest_stop_id(lat: float, lon: float, coordinates: Dict[str, Tuple[float, float]]) -> Optional[str]:
    if not coordinates:
        return None
    return min(
        coordinates.keys(),
        key=lambda sid: (lat - coordinates[sid][0]) ** 2 + (lon - coordinates[sid][1]) ** 2,
    )


def format_path_table(path_ids: List[str], stop_lookup: Dict[str, Dict[str, object]]) -> pd.DataFrame:
    rows = []
    for idx, stop_id in enumerate(path_ids, start=1):
        info = stop_lookup.get(str(stop_id), {})
        rows.append(
            {
                "Step": idx,
                "Stop ID": str(stop_id),
                "Stop name": info.get("stop_name", "Unknown"),
                "Lat": info.get("stop_lat"),
                "Lon": info.get("stop_lon"),
            }
        )
    return pd.DataFrame(rows)


def route_text(path_ids: List[str], stop_lookup: Dict[str, Dict[str, object]]) -> str:
    names = []
    for stop_id in path_ids:
        info = stop_lookup.get(str(stop_id), {})
        names.append(info.get("stop_name", str(stop_id)))
    return " → ".join(names)


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tìm đường đi tàu điện / bus",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 Ứng dụng tìm đường đi tàu điện / bus")
st.caption("Dùng dữ liệu và thuật toán đã có trong project để tìm lộ trình giữa hai điểm.")

with st.sidebar:
    st.header("Thiết lập")
    st.write("**Database**")
    st.code(DB_PATH)

    start_time = st.time_input("Giờ xuất phát", value=datetime.now().time().replace(second=0, microsecond=0))
    start_time_str = start_time.strftime("%H:%M:%S")

    st.divider()
    st.write("**Cách dùng**")
    st.write("1. Chọn nhập tọa độ hoặc chọn bến.")
    st.write("2. Bấm nút tìm đường đi.")
    st.write("3. Xem danh sách các bến đi qua.")

# Load data once
with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        stop_times, graph, coordinates = load_route_objects(DB_PATH)
        stop_lookup = make_stop_lookup(DB_PATH)
        stops_df = load_stops_table(DB_PATH)
    except Exception as exc:
        st.error(f"Không thể nạp dữ liệu từ database: {exc}")
        st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Số bến", f"{len(stop_lookup):,}")
col2.metric("Số cạnh graph", f"{sum(len(v) for v in graph.values()):,}")
col3.metric("Số dòng stop_times", f"{len(stop_times):,}")

mode = st.radio("Chọn kiểu nhập", ["Nhập tọa độ", "Chọn bến có sẵn"], horizontal=True)

if mode == "Nhập tọa độ":
    left, right = st.columns(2)
    with left:
        st.subheader("Điểm đi")
        start_lat = st.number_input("Vĩ độ xuất phát", value=DEFAULT_START_LAT, format="%.6f")
        start_lon = st.number_input("Kinh độ xuất phát", value=DEFAULT_START_LON, format="%.6f")
    with right:
        st.subheader("Điểm đến")
        goal_lat = st.number_input("Vĩ độ điểm đến", value=DEFAULT_GOAL_LAT, format="%.6f")
        goal_lon = st.number_input("Kinh độ điểm đến", value=DEFAULT_GOAL_LON, format="%.6f")

    start_id = nearest_stop_id(start_lat, start_lon, coordinates)
    goal_id = nearest_stop_id(goal_lat, goal_lon, coordinates)

    info_left, info_right = st.columns(2)
    with info_left:
        if start_id and start_id in stop_lookup:
            st.info(
                f"Bến gần nhất cho điểm đi: **{stop_lookup[start_id]['stop_name']}** (ID: `{start_id}`)"
            )
        else:
            st.warning("Không tìm được bến gần nhất cho điểm đi.")
    with info_right:
        if goal_id and goal_id in stop_lookup:
            st.info(
                f"Bến gần nhất cho điểm đến: **{stop_lookup[goal_id]['stop_name']}** (ID: `{goal_id}`)"
            )
        else:
            st.warning("Không tìm được bến gần nhất cho điểm đến.")

else:
    options = [f"{row.stop_name}  ·  {row.stop_id}" for row in stops_df.itertuples(index=False)]
    choice_start = st.selectbox("Bến xuất phát", options, index=0)
    choice_goal = st.selectbox("Bến đích", options, index=min(1, len(options) - 1))
    start_id = choice_start.split("·")[-1].strip()
    goal_id = choice_goal.split("·")[-1].strip()

    start_info = stop_lookup.get(start_id)
    goal_info = stop_lookup.get(goal_id)
    if start_info:
        st.info(f"Xuất phát: **{start_info['stop_name']}** (ID: `{start_id}`)")
    if goal_info:
        st.info(f"Điểm đến: **{goal_info['stop_name']}** (ID: `{goal_id}`)")

run = st.button("Tìm đường đi", type="primary", use_container_width=True)

if run:
    if not start_id or not goal_id:
        st.error("Không thể xác định bến xuất phát hoặc bến đích.")
        st.stop()

    if start_id not in coordinates:
        st.error(f"Bến xuất phát `{start_id}` không có trong tập tọa độ dùng cho graph.")
        st.stop()

    if goal_id not in coordinates:
        st.error(f"Bến đích `{goal_id}` không có trong tập tọa độ dùng cho graph.")
        st.stop()

    with st.spinner("Đang chạy thuật toán A*..."):
        try:
            path = a_star(
                graph=graph,
                start=start_id,
                goal=goal_id,
                coordinates=coordinates,
                start_time=start_time_str,
            )
        except Exception as exc:
            st.error(f"Lỗi khi chạy tìm đường đi: {exc}")
            st.stop()

    if not path:
        st.warning("Không tìm được đường đi phù hợp từ dữ liệu hiện tại.")
    else:
        st.success(f"Tìm thấy đường đi với {len(path)} bến.")

        route_df = format_path_table(path, stop_lookup)
        st.subheader("Lộ trình")
        st.code(route_text(path, stop_lookup), language="text")

        route_map_df = route_df.dropna(subset=["Lat", "Lon"])[["Lat", "Lon"]].rename(
            columns={"Lat": "lat", "Lon": "lon"}
        )
        if not route_map_df.empty:
            st.map(route_map_df, zoom=13)

        st.dataframe(route_df, use_container_width=True, hide_index=True)

        with st.expander("Xem mã stop_id thô"):
            st.write(path)

st.divider()
st.caption(
    "Gợi ý triển khai: chạy `streamlit run app.py` trong thư mục gốc của project, cùng cấp với `core/`, `utils/` và `src/`."
)
