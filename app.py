
import os
import sys
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# Make the project importable when running: streamlit run app.py
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
for path in (BASE_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Project modules under src/
from data_engine.data_process import load_data, normalize_route_paths_dataframe
from logic.router import a_star_search


DEFAULT_START_LAT = 50.8466
DEFAULT_START_LON = 4.3528
DEFAULT_GOAL_LAT = 50.8456
DEFAULT_GOAL_LON = 4.3572
DEFAULT_MAP_CENTER = (50.8503, 4.3517)


@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "pin_mode": "start",  # "start" or "goal"
        "map_start_coords": None,  # {"lat": ..., "lon": ...}
        "map_goal_coords": None,
        "map_start_nearest": None,
        "map_goal_nearest": None,
        "manual_start_id": None,
        "manual_goal_id": None,
        "route_result": None,
        "last_processed_click": None,
        "active_input_mode": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_route_result() -> None:
    st.session_state.route_result = None


def set_start_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_start_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_start_nearest = nearest_stop
    clear_route_result()


def set_goal_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_goal_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_goal_nearest = nearest_stop
    clear_route_result()


def reset_all() -> None:
    for key in [
        "pin_mode",
        "map_start_coords",
        "map_goal_coords",
        "map_start_nearest",
        "map_goal_nearest",
        "manual_start_id",
        "manual_goal_id",
        "route_result",
        "last_processed_click",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


# -----------------------------------------------------------------------------
# Data loading helpers
# -----------------------------------------------------------------------------
def resolve_db_path() -> Path:
    candidates = [
        BASE_DIR / "src" / "data_engine" / "stib_database.db",
        BASE_DIR / "data" / "stib_database.db",
        BASE_DIR / "src" / "data" / "stib_database.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


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
    df["stop_name"] = df["stop_name"].astype(str)
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

    route_paths = normalize_route_paths_dataframe(route_paths)
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


def build_route_segments(path_nodes: List[object]) -> pd.DataFrame:
    """Group consecutive nodes by route_id to make the line plan easier to read."""
    if not path_nodes or len(path_nodes) < 2:
        return pd.DataFrame(columns=["Tuyến", "Từ", "Đến", "Số bến", "Thời gian (phút)"])

    segments = []
    seg_start_idx = 1  # path_nodes[0] is the walking-in/start anchor

    def route_of(node) -> str:
        return str(getattr(node, "route_id", None) or "---")

    current_route = route_of(path_nodes[1])

    for idx in range(2, len(path_nodes)):
        nxt_route = route_of(path_nodes[idx])
        if nxt_route != current_route:
            start_node = path_nodes[seg_start_idx]
            end_node = path_nodes[idx - 1]
            segments.append(
                {
                    "Tuyến": current_route,
                    "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"),
                    "Đến": getattr(end_node.stop, "name", "---"),
                    "Số bến": idx - seg_start_idx,
                    "Thời gian (phút)": round(float(end_node.g - path_nodes[seg_start_idx - 1].g), 2),
                }
            )
            seg_start_idx = idx
            current_route = nxt_route

    end_node = path_nodes[-1]
    segments.append(
        {
            "Tuyến": current_route,
            "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"),
            "Đến": getattr(end_node.stop, "name", "---"),
            "Số bến": len(path_nodes) - seg_start_idx,
            "Thời gian (phút)": round(float(end_node.g - path_nodes[seg_start_idx - 1].g), 2),
        }
    )

    return pd.DataFrame(segments)


def get_current_coords(
    input_mode: str,
    stop_lookup: Dict[str, Dict[str, object]],
) -> Tuple[Optional[Coords], Optional[Coords], Optional[str], Optional[str]]:
    """
    Return (start_coords, goal_coords, start_label, goal_label) based on current UI mode.
    """
    if input_mode == "Ghim trên bản đồ":
        start = st.session_state.map_start_coords
        goal = st.session_state.map_goal_coords

        start_coords = Coords(start["lat"], start["lon"]) if start else None
        goal_coords = Coords(goal["lat"], goal["lon"]) if goal else None

        start_label = None
        goal_label = None
        if start_coords:
            nearest = st.session_state.map_start_nearest or ""
            start_label = f"{start_coords.lat:.6f}, {start_coords.lon:.6f}"
            if nearest and nearest in stop_lookup:
                start_label += f"  •  gần bến {stop_lookup[nearest]['stop_name']}"
        if goal_coords:
            nearest = st.session_state.map_goal_nearest or ""
            goal_label = f"{goal_coords.lat:.6f}, {goal_coords.lon:.6f}"
            if nearest and nearest in stop_lookup:
                goal_label += f"  •  gần bến {stop_lookup[nearest]['stop_name']}"

        return start_coords, goal_coords, start_label, goal_label

    # Manual stop selection
    start_id = st.session_state.manual_start_id
    goal_id = st.session_state.manual_goal_id

    start_info = stop_lookup.get(start_id) if start_id else None
    goal_info = stop_lookup.get(goal_id) if goal_id else None

    start_coords = (
        Coords(float(start_info["stop_lat"]), float(start_info["stop_lon"])) if start_info else None
    )
    goal_coords = (
        Coords(float(goal_info["stop_lat"]), float(goal_info["stop_lon"])) if goal_info else None
    )

    start_label = f"{start_info['stop_name']} (ID: {start_id})" if start_info else None
    goal_label = f"{goal_info['stop_name']} (ID: {goal_id})" if goal_info else None
    return start_coords, goal_coords, start_label, goal_label


def build_route_map(
    all_stops: List[object],
    stop_lookup: Dict[str, Dict[str, object]],
    path_nodes: Optional[List[object]] = None,
    start_coords: Optional[Coords] = None,
    goal_coords: Optional[Coords] = None,
    start_nearest_stop: Optional[str] = None,
    goal_nearest_stop: Optional[str] = None,
) -> folium.Map:
    coords = [(float(stop.lat), float(stop.lon)) for stop in all_stops if getattr(stop, "lat", None) is not None and getattr(stop, "lon", None) is not None]
    if coords:
        center_lat = sum(lat for lat, _ in coords) / len(coords)
        center_lon = sum(lon for _, lon in coords) / len(coords)
    else:
        center_lat, center_lon = DEFAULT_MAP_CENTER

    if start_coords:
        center_lat, center_lon = start_coords.lat, start_coords.lon
    elif goal_coords:
        center_lat, center_lon = goal_coords.lat, goal_coords.lon

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        control_scale=True,
        tiles="OpenStreetMap",
        width="100%",
        height=650,
    )

    # Route polyline and route stop markers
    route_points = []
    if path_nodes:
        path_rows = collect_route_rows(path_nodes, stop_lookup)
        for row in path_rows:
            lat = row.get("Lat")
            lon = row.get("Lon")
            if lat is None or lon is None:
                continue
            route_points.append((lat, lon))

        if len(route_points) >= 2:
            folium.PolyLine(
                route_points,
                color="#1f77b4",
                weight=5,
                opacity=0.85,
                tooltip="Lộ trình",
            ).add_to(m)

        for idx, row in enumerate(path_rows):
            lat = row.get("Lat")
            lon = row.get("Lon")
            if lat is None or lon is None:
                continue

            route_id = row.get("Route", "---")
            stop_name = row.get("Stop name", "---")
            stop_id = row.get("Stop ID", "---")

            is_first = idx == 0
            is_last = idx == len(path_rows) - 1
            color = "blue"
            icon = "circle"
            prefix = "fa"
            if is_first:
                color = "green"
                icon = "play"
            elif is_last:
                color = "red"
                icon = "flag"

            popup_html = f"""
            <b>{'Điểm đầu của lộ trình' if is_first else ('Điểm cuối của lộ trình' if is_last else 'Bến trung gian')}</b><br>
            {stop_name}<br>
            ID: {stop_id}<br>
            Tuyến: {route_id}<br>
            ({lat:.6f}, {lon:.6f})
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{stop_name} · {route_id}",
                icon=folium.Icon(color=color, icon=icon, prefix=prefix),
            ).add_to(m)

    # User-selected start/end positions
    if start_coords is not None:
        popup = f"""
        <b>Điểm đi đã ghim</b><br>
        ({start_coords.lat:.6f}, {start_coords.lon:.6f})<br>
        {"Gần bến: " + stop_lookup[start_nearest_stop]["stop_name"] if start_nearest_stop in stop_lookup else ""}
        """
        folium.Marker(
            location=[start_coords.lat, start_coords.lon],
            popup=folium.Popup(popup, max_width=320),
            tooltip="Điểm đi",
            icon=folium.Icon(color="green", icon="star", prefix="fa"),
        ).add_to(m)

    if goal_coords is not None:
        popup = f"""
        <b>Điểm đến đã ghim</b><br>
        ({goal_coords.lat:.6f}, {goal_coords.lon:.6f})<br>
        {"Gần bến: " + stop_lookup[goal_nearest_stop]["stop_name"] if goal_nearest_stop in stop_lookup else ""}
        """
        folium.Marker(
            location=[goal_coords.lat, goal_coords.lon],
            popup=folium.Popup(popup, max_width=320),
            tooltip="Điểm đến",
            icon=folium.Icon(color="red", icon="flag", prefix="fa"),
        ).add_to(m)

    # Helper lines from clicked points to the nearest stop in the computed path
    if path_nodes and start_coords is not None:
        first_stop = path_nodes[0].stop
        if first_stop is not None:
            folium.PolyLine(
                [(start_coords.lat, start_coords.lon), (first_stop.lat, first_stop.lon)],
                color="#2ca02c",
                weight=3,
                dash_array="6, 6",
                opacity=0.75,
                tooltip="Đoạn đi bộ vào bến",
            ).add_to(m)

    if path_nodes and goal_coords is not None:
        last_stop = path_nodes[-1].stop
        if last_stop is not None:
            folium.PolyLine(
                [(last_stop.lat, last_stop.lon), (goal_coords.lat, goal_coords.lon)],
                color="#d62728",
                weight=3,
                dash_array="6, 6",
                opacity=0.75,
                tooltip="Đoạn đi bộ ra điểm đến",
            ).add_to(m)

    # Fit bounds if we have any coordinates to show
    bound_points = []
    if route_points:
        bound_points.extend(route_points)
    if start_coords is not None:
        bound_points.append((start_coords.lat, start_coords.lon))
    if goal_coords is not None:
        bound_points.append((goal_coords.lat, goal_coords.lon))

    if bound_points:
        m.fit_bounds(bound_points, padding=(30, 30))

    return m


def render_map(m: folium.Map) -> Dict[str, object]:
    return st_folium(m, width="100%", height=650, key="interactive_map")


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tìm đường đi tàu điện / bus",
    page_icon="🚌",
    layout="wide",
)

init_state()

st.title("🚌 Ứng dụng tìm đường đi tàu điện / bus")

db_path = resolve_db_path()

with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        route_paths, all_stops, coordinates = load_route_objects(str(db_path))
        stop_lookup = make_stop_lookup(str(db_path))
        stops_df = load_stops_table(str(db_path))
    except Exception as exc:
        st.error(f"Không thể nạp dữ liệu từ database: {exc}")
        st.stop()

# Main map first
st.subheader("Bản đồ")
input_mode = st.radio(
    "Cách chọn điểm",
    ["Ghim trên bản đồ", "Chọn bến có sẵn"],
    horizontal=True,
    key="input_mode_radio",
)

if st.session_state.active_input_mode is not None and st.session_state.active_input_mode != input_mode:
    clear_route_result()
st.session_state.active_input_mode = input_mode

start_coords, goal_coords, start_label, goal_label = get_current_coords(input_mode, stop_lookup)

nearest_start_stop = None
nearest_goal_stop = None
if input_mode == "Ghim trên bản đồ":
    if start_coords is not None:
        nearest_start_stop = nearest_stop_id(start_coords.lat, start_coords.lon, coordinates)
    if goal_coords is not None:
        nearest_goal_stop = nearest_stop_id(goal_coords.lat, goal_coords.lon, coordinates)

map_obj = build_route_map(
    all_stops=all_stops,
    stop_lookup=stop_lookup,
    path_nodes=st.session_state.route_result["path"] if st.session_state.route_result else None,
    start_coords=start_coords,
    goal_coords=goal_coords,
    start_nearest_stop=nearest_start_stop,
    goal_nearest_stop=nearest_goal_stop,
)
map_state = render_map(map_obj)

# Capture map click for pin mode
clicked = (map_state or {}).get("last_clicked")
if input_mode == "Ghim trên bản đồ" and clicked:
    click_key = (round(float(clicked["lat"]), 6), round(float(clicked["lng"]), 6))
    if st.session_state.last_processed_click != click_key:
        st.session_state.last_processed_click = click_key
        target = st.session_state.pin_mode
        nearest = nearest_stop_id(float(clicked["lat"]), float(clicked["lng"]), coordinates)
        if target == "start":
            set_start_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
        else:
            set_goal_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
        st.rerun()


# Controls below the map
st.subheader("Điều khiển")

if input_mode == "Ghim trên bản đồ":
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Đặt điểm đi", use_container_width=True):
            st.session_state.pin_mode = "start"
    with c2:
        if st.button("Đặt điểm đến", use_container_width=True):
            st.session_state.pin_mode = "goal"
    with c3:
        if st.button("Clear", use_container_width=True):
            reset_all()

    pin_label = "Điểm đi" if st.session_state.pin_mode == "start" else "Điểm đến"
    st.info(f"Chế độ click hiện tại: **{pin_label}**")
else:
    left, right = st.columns(2)
    options = [f"{row.stop_name}  ·  {row.stop_id}" for row in stops_df.itertuples(index=False)]
    with left:
        choice_start = st.selectbox(
            "Bến xuất phát",
            options,
            index=0,
            key="manual_start_selector",
        )
        chosen_start_id = choice_start.split("·")[-1].strip()
        if st.session_state.manual_start_id != chosen_start_id:
            st.session_state.manual_start_id = chosen_start_id
            clear_route_result()
        start_info = stop_lookup.get(st.session_state.manual_start_id)
        if start_info:
            st.success(f"Xuất phát: **{start_info['stop_name']}** (ID: `{st.session_state.manual_start_id}`)")
    with right:
        choice_goal = st.selectbox(
            "Bến đích",
            options,
            index=min(1, len(options) - 1),
            key="manual_goal_selector",
        )
        chosen_goal_id = choice_goal.split("·")[-1].strip()
        if st.session_state.manual_goal_id != chosen_goal_id:
            st.session_state.manual_goal_id = chosen_goal_id
            clear_route_result()
        goal_info = stop_lookup.get(st.session_state.manual_goal_id)
        if goal_info:
            st.success(f"Điểm đến: **{goal_info['stop_name']}** (ID: `{st.session_state.manual_goal_id}`)")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Clear", use_container_width=True):
            reset_all()
    with c2:
        st.caption("Bạn vẫn có thể tìm đường ngay sau khi chọn bến ở phần này.")

# Show current coordinates summary
summary_cols = st.columns(2)
with summary_cols[0]:
    if start_coords is not None:
        st.write("**Điểm đi hiện tại**")
        st.code(start_label or f"{start_coords.lat:.6f}, {start_coords.lon:.6f}", language="text")
    else:
        st.warning("Chưa có điểm đi.")
with summary_cols[1]:
    if goal_coords is not None:
        st.write("**Điểm đến hiện tại**")
        st.code(goal_label or f"{goal_coords.lat:.6f}, {goal_coords.lon:.6f}", language="text")
    else:
        st.warning("Chưa có điểm đến.")

search_cols = st.columns([1, 1, 2])
with search_cols[0]:
    search_clicked = st.button("Tìm đường đi", type="primary", use_container_width=True)
with search_cols[1]:
    if st.button("Clear kết quả", use_container_width=True):
        clear_route_result()
        st.rerun()

# Execute route search
if search_clicked:
    start_coords, goal_coords, start_label, goal_label = get_current_coords(input_mode, stop_lookup)

    if start_coords is None or goal_coords is None:
        st.error("Bạn cần chọn đủ điểm đi và điểm đến trước khi tìm đường.")
    else:
        with st.spinner("Đang chạy thuật toán A*..."):
            try:
                results = a_star_search(start_coords, goal_coords, all_stops)
            except Exception as exc:
                st.error(f"Lỗi khi chạy tìm đường đi: {exc}")
                st.stop()

        if not results:
            st.warning("Không tìm được đường đi phù hợp từ dữ liệu hiện tại.")
            st.session_state.route_result = None
        else:
            best = results[0]
            st.session_state.route_result = best

# Present result if available
if st.session_state.route_result:
    best = st.session_state.route_result
    path_nodes = best["path"]

    st.subheader("Kết quả")
    st.success(
        f"Tìm thấy lộ trình với {len(path_nodes)} bến. Tổng thời gian ước tính: {best['duration']:.2f} phút."
    )

    route_segments = build_route_segments(path_nodes)
    if not route_segments.empty:
        st.write("**Các tuyến xe trong lộ trình**")
        st.dataframe(route_segments, use_container_width=True, hide_index=True)

        route_line = "  •  ".join(
            f"Tuyến {row['Tuyến']} ({row['Từ']} → {row['Đến']})"
            for _, row in route_segments.iterrows()
        )
        st.info(route_line)

    path_rows = collect_route_rows(path_nodes, stop_lookup)
    if path_rows:
        with st.expander("Chi tiết từng bến trong lộ trình", expanded=False):
            st.dataframe(pd.DataFrame(path_rows), use_container_width=True, hide_index=True)

    final_walk_minutes = best["duration"] - float(path_nodes[-1].g)
    if final_walk_minutes > 0.1:
        st.caption(f"Còn khoảng {final_walk_minutes:.1f} phút đi bộ từ bến cuối tới điểm đến.")

st.divider()

with st.expander("Thông tin dữ liệu", expanded=False):
    info_cols = st.columns(3)
    info_cols[0].metric("Số bến", f"{len(stop_lookup):,}")
    info_cols[1].metric("Số node graph", f"{len(all_stops):,}")
    info_cols[2].metric("Số dòng route_paths", f"{len(route_paths):,}")
    st.write(f"**Database đang dùng:** `{db_path}`")
