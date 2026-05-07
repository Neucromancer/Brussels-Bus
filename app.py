import os
import sys
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st
import folium
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# Make the project importable when running: streamlit run app.py
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
for path in (BASE_DIR, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# Project modules under src/
from src.data_engine.data_process import load_data
from src.logic.router import a_star_search


DB_PATH = os.path.join(BASE_DIR, "src", "data_engine", "stib_database.db")
DEFAULT_START_LAT = 50.8466
DEFAULT_START_LON = 4.3528
DEFAULT_GOAL_LAT = 50.8456
DEFAULT_GOAL_LON = 4.3572


@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float


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
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    return df.drop_duplicates(subset=["stop_id"]).sort_values(["stop_name", "stop_id"])


@st.cache_data(show_spinner=False)
def load_route_objects(db_path: str):
    """Load route_paths dataframe and convert it to the stop graph used by A*."""
    conn = sqlite3.connect(db_path)
    try:
        route_paths = pd.read_sql_query("SELECT * FROM route_paths", conn)
    finally:
        conn.close()

    route_paths["stop_id"] = route_paths["stop_id"].astype(str)
    route_paths["route_name"] = route_paths["route_name"].astype(str)
    route_paths["direction"] = pd.to_numeric(route_paths["direction"], errors="coerce")
    route_paths["stop_order"] = pd.to_numeric(route_paths["stop_order"], errors="coerce")
    route_paths["stop_lat"] = pd.to_numeric(route_paths["stop_lat"], errors="coerce")
    route_paths["stop_lon"] = pd.to_numeric(route_paths["stop_lon"], errors="coerce")
    route_paths = route_paths.dropna(subset=["stop_order", "stop_lat", "stop_lon"])
    route_paths["direction"] = route_paths["direction"].astype(int)
    route_paths["stop_order"] = route_paths["stop_order"].astype(int)

    all_stops = load_data(route_paths)
    coordinates = {str(stop.id): (float(stop.lat), float(stop.lon)) for stop in all_stops}
    return route_paths, all_stops, coordinates


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


def collect_route_rows(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for idx, node in enumerate(path_nodes, start=1):
        stop = getattr(node, "stop", None)
        if stop is None:
            continue

        stop_id = str(getattr(stop, "id", ""))
        info = stop_lookup.get(stop_id, {})
        stop_name = info.get("stop_name") or getattr(stop, "name", None) or f"Stop {stop_id}"

        lat = getattr(stop, "lat", None)
        lon = getattr(stop, "lon", None)
        if lat is None:
            lat = info.get("stop_lat")
        if lon is None:
            lon = info.get("stop_lon")

        rows.append(
            {
                "Step": idx,
                "Stop ID": stop_id,
                "Stop name": stop_name,
                "Lat": float(lat) if lat is not None else None,
                "Lon": float(lon) if lon is not None else None,
                "Route": getattr(node, "route_id", None) or "---",
                "Time (min)": round(float(getattr(node, "g", 0.0)), 2),
            }
        )
    return rows


def format_path_table(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(collect_route_rows(path_nodes, stop_lookup))


def route_text(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> str:
    rows = collect_route_rows(path_nodes, stop_lookup)
    return " → ".join(row["Stop name"] for row in rows)


def build_route_map(
    path_nodes: List[object],
    stop_lookup: Dict[str, Dict[str, object]],
    start_id: str,
    goal_id: str,
) -> Optional[folium.Map]:
    rows = collect_route_rows(path_nodes, stop_lookup)
    coords = []
    route_points = []

    for row in rows:
        lat = row.get("Lat")
        lon = row.get("Lon")
        if lat is None or lon is None:
            continue
        lat = float(lat)
        lon = float(lon)
        coords.append((lat, lon))
        route_points.append(
            {
                "stop_id": str(row["Stop ID"]),
                "stop_name": str(row["Stop name"]),
                "lat": lat,
                "lon": lon,
            }
        )

    if not coords:
        return None

    center_lat = sum(lat for lat, _ in coords) / len(coords)
    center_lon = sum(lon for _, lon in coords) / len(coords)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14, control_scale=True, tiles="OpenStreetMap", width="100%", height=620)

    if len(coords) >= 2:
        folium.PolyLine(
            coords,
            color="#1f77b4",
            weight=5,
            opacity=0.85,
            tooltip="Lộ trình",
        ).add_to(m)

    for i, point in enumerate(route_points):
        is_start = point["stop_id"] == str(start_id)
        is_goal = point["stop_id"] == str(goal_id)

        if is_start:
            color = "green"
            icon = "play"
            prefix = "fa"
            label = "Điểm đi"
        elif is_goal:
            color = "red"
            icon = "flag"
            prefix = "fa"
            label = "Điểm đến"
        else:
            color = "blue"
            icon = "circle"
            prefix = "fa"
            label = f"Bến {i + 1}"

        popup_html = f"""
        <b>{label}</b><br>
        {point["stop_name"]}<br>
        ID: {point["stop_id"]}<br>
        ({point["lat"]:.6f}, {point["lon"]:.6f})
        """
        folium.Marker(
            location=[point["lat"], point["lon"]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=point["stop_name"],
            icon=folium.Icon(color=color, icon=icon, prefix=prefix),
        ).add_to(m)

    m.fit_bounds(coords, padding=(30, 30))
    return m


def render_folium_map(m: folium.Map, height: int = 620) -> None:
    """Render folium map inside Streamlit without leaving a blank container behind."""
    map_html = m.get_root().render()
    components.html(map_html, height=height, scrolling=False)


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tìm đường đi tàu điện / bus",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 Ứng dụng tìm đường đi tàu điện / bus")
st.caption("Dùng dữ liệu và thuật toán trong src/ để tìm lộ trình giữa hai điểm.")

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
    st.write("3. Xem bản đồ Folium lộ trình.")

# Load data once
with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        route_paths, all_stops, coordinates = load_route_objects(DB_PATH)
        stop_lookup = make_stop_lookup(DB_PATH)
        stops_df = load_stops_table(DB_PATH)
    except Exception as exc:
        st.error(f"Không thể nạp dữ liệu từ database: {exc}")
        st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Số bến", f"{len(stop_lookup):,}")
col2.metric("Số node graph", f"{len(all_stops):,}")
col3.metric("Số dòng route_paths", f"{len(route_paths):,}")

mode = st.radio("Chọn kiểu nhập", ["Nhập tọa độ", "Chọn bến có sẵn"], horizontal=True)

start_id = None
goal_id = None
start_coords = None
goal_coords = None

if mode == "Nhập tọa độ":
    left, right = st.columns(2)
    with left:
        st.subheader("Điểm đi")
        start_lat = float(st.number_input("Vĩ độ xuất phát", value=DEFAULT_START_LAT, format="%.6f"))
        start_lon = float(st.number_input("Kinh độ xuất phát", value=DEFAULT_START_LON, format="%.6f"))
    with right:
        st.subheader("Điểm đến")
        goal_lat = float(st.number_input("Vĩ độ điểm đến", value=DEFAULT_GOAL_LAT, format="%.6f"))
        goal_lon = float(st.number_input("Kinh độ điểm đến", value=DEFAULT_GOAL_LON, format="%.6f"))

    start_coords = Coords(start_lat, start_lon)
    goal_coords = Coords(goal_lat, goal_lon)
    start_id = nearest_stop_id(start_lat, start_lon, coordinates)
    goal_id = nearest_stop_id(goal_lat, goal_lon, coordinates)

    info_left, info_right = st.columns(2)
    with info_left:
        if start_id and start_id in stop_lookup:
            st.info(f"Bến gần nhất cho điểm đi: **{stop_lookup[start_id]['stop_name']}** (ID: `{start_id}`)")
        else:
            st.warning("Không tìm được bến gần nhất cho điểm đi.")
    with info_right:
        if goal_id and goal_id in stop_lookup:
            st.info(f"Bến gần nhất cho điểm đến: **{stop_lookup[goal_id]['stop_name']}** (ID: `{goal_id}`)")
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
        start_coords = Coords(float(start_info['stop_lat']), float(start_info['stop_lon']))
    if goal_info:
        st.info(f"Điểm đến: **{goal_info['stop_name']}** (ID: `{goal_id}`)")
        goal_coords = Coords(float(goal_info['stop_lat']), float(goal_info['stop_lon']))

run = st.button("Tìm đường đi", type="primary", use_container_width=True)

if run:
    if not start_id or not goal_id or start_coords is None or goal_coords is None:
        st.error("Không thể xác định bến xuất phát hoặc bến đích.")
        st.stop()

    with st.spinner("Đang chạy thuật toán A*..."):
        try:
            # A* trong src/ đòi hỏi tọa độ phải là số thực, nên ép kiểu ở đây
            start_coords = Coords(float(start_coords.lat), float(start_coords.lon))
            goal_coords = Coords(float(goal_coords.lat), float(goal_coords.lon))
            results = a_star_search(start_coords, goal_coords, all_stops)
        except Exception as exc:
            st.error(f"Lỗi khi chạy tìm đường đi: {exc}")
            st.stop()

    if not results:
        st.warning("Không tìm được đường đi phù hợp từ dữ liệu hiện tại.")
    else:
        best = results[0]
        path_nodes = best["path"]

        st.success(f"Tìm thấy đường đi với {len(path_nodes)} bến. Tổng thời gian ước tính: {best['duration']:.2f} phút.")

        route_text_value = route_text(path_nodes, stop_lookup)
        if route_text_value:
            st.code(route_text_value, language="text")
        else:
            st.info("Không trích xuất được tên bến từ lộ trình này.")

        map_obj = build_route_map(path_nodes, stop_lookup, start_id=start_id, goal_id=goal_id)
        if map_obj is not None:
            st.subheader("Bản đồ lộ trình")
            render_folium_map(map_obj, height=620)
        else:
            st.info("Không đủ tọa độ để vẽ bản đồ cho lộ trình này.")

st.divider()
