from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import folium
import pandas as pd


def nearest_stop_id(lat: float, lon: float, coordinates: Dict[str, Tuple[float, float]]) -> Optional[str]:
    if not coordinates:
        return None
    return min(
        coordinates.keys(),
        key=lambda sid: (lat - coordinates[sid][0]) ** 2 + (lon - coordinates[sid][1]) ** 2,
    )


def collect_route_rows(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

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


def route_text(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> str:
    rows = collect_route_rows(path_nodes, stop_lookup)
    if not rows:
        return ""

    parts = []
    for idx, row in enumerate(rows):
        label = row["Stop name"]
        route = row["Route"]
        if idx == 0:
            parts.append(f"[{label}]")
        else:
            parts.append(f"({route}) {label}")
    return " → ".join(parts)


def route_step_table(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> pd.DataFrame:
    rows = collect_route_rows(path_nodes, stop_lookup)
    if not rows:
        return pd.DataFrame(columns=["Step", "Stop name", "Route", "Time (min)"])
    return pd.DataFrame(rows)[["Step", "Stop name", "Route", "Time (min)", "Stop ID", "Lat", "Lon"]]


def route_segment_table(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> pd.DataFrame:
    rows = collect_route_rows(path_nodes, stop_lookup)
    if len(rows) < 2:
        return pd.DataFrame(columns=["Segment", "Route", "From", "To", "Duration (min)"])

    segments = []
    prev = rows[0]
    for idx, current in enumerate(rows[1:], start=1):
        route = current["Route"]
        segments.append(
            {
                "Segment": idx,
                "Route": route,
                "From": prev["Stop name"],
                "To": current["Stop name"],
                "Duration (min)": round(float(current["Time (min)"]) - float(prev["Time (min)"]), 2),
            }
        )
        prev = current

    return pd.DataFrame(segments)


def _add_marker(
    m: folium.Map,
    lat: float,
    lon: float,
    label: str,
    color: str,
    icon: str,
    tooltip: Optional[str] = None,
    popup: Optional[str] = None,
) -> None:
    folium.Marker(
        location=[lat, lon],
        tooltip=tooltip or label,
        popup=folium.Popup(popup or label, max_width=320),
        icon=folium.Icon(color=color, icon=icon, prefix="fa"),
    ).add_to(m)


def build_selection_map(
    start_coords,
    goal_coords,
    start_label: str = "Điểm đi",
    goal_label: str = "Điểm đến",
) -> Optional[folium.Map]:
    points = []
    if start_coords is not None:
        points.append((float(start_coords.lat), float(start_coords.lon)))
    if goal_coords is not None:
        points.append((float(goal_coords.lat), float(goal_coords.lon)))

    if not points:
        return None

    center_lat = sum(p[0] for p in points) / len(points)
    center_lon = sum(p[1] for p in points) / len(points)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        control_scale=True,
        tiles="OpenStreetMap",
        width="100%",
        height=620,
    )

    if start_coords is not None:
        _add_marker(
            m,
            float(start_coords.lat),
            float(start_coords.lon),
            start_label,
            "green",
            "play",
            tooltip=start_label,
            popup=f"<b>{start_label}</b><br>({float(start_coords.lat):.6f}, {float(start_coords.lon):.6f})",
        )
    if goal_coords is not None:
        _add_marker(
            m,
            float(goal_coords.lat),
            float(goal_coords.lon),
            goal_label,
            "red",
            "flag",
            tooltip=goal_label,
            popup=f"<b>{goal_label}</b><br>({float(goal_coords.lat):.6f}, {float(goal_coords.lon):.6f})",
        )

    if len(points) == 2:
        folium.PolyLine(points, color="#6c757d", weight=4, opacity=0.75, tooltip="Khoảng cách đã chọn").add_to(m)

    try:
        from folium.plugins import MousePosition, ClickForMarker, LatLngPopup

        MousePosition(
            position="bottomright",
            separator=" | ",
            empty_string="Di chuột lên bản đồ để xem tọa độ",
            num_digits=6,
            prefix="Lat/Lon:",
        ).add_to(m)
        ClickForMarker(popup="Điểm bạn vừa ghim").add_to(m)
        LatLngPopup().add_to(m)
    except Exception:
        pass

    return m


def build_route_map(
    path_nodes: List[object],
    stop_lookup: Dict[str, Dict[str, object]],
    start_coords,
    goal_coords,
    start_id: str,
    goal_id: str,
) -> Optional[folium.Map]:
    rows = collect_route_rows(path_nodes, stop_lookup)
    coords = []
    route_points = []

    if start_coords is not None:
        coords.append((float(start_coords.lat), float(start_coords.lon)))
    if goal_coords is not None:
        coords.append((float(goal_coords.lat), float(goal_coords.lon)))

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
                "route": str(row["Route"]),
                "step": int(row["Step"]),
            }
        )

    if not coords:
        return None

    center_lat = sum(lat for lat, _ in coords) / len(coords)
    center_lon = sum(lon for _, lon in coords) / len(coords)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        control_scale=True,
        tiles="OpenStreetMap",
        width="100%",
        height=620,
    )

    route_line = []
    if start_coords is not None:
        route_line.append((float(start_coords.lat), float(start_coords.lon)))
    route_line.extend((p["lat"], p["lon"]) for p in route_points)
    if goal_coords is not None:
        route_line.append((float(goal_coords.lat), float(goal_coords.lon)))

    if len(route_line) >= 2:
        folium.PolyLine(
            route_line,
            color="#1f77b4",
            weight=5,
            opacity=0.9,
            tooltip="Lộ trình",
        ).add_to(m)

    if start_coords is not None:
        _add_marker(
            m,
            float(start_coords.lat),
            float(start_coords.lon),
            "Điểm đi",
            "green",
            "play",
            tooltip="Điểm đi",
            popup=f"<b>Điểm đi</b><br>({float(start_coords.lat):.6f}, {float(start_coords.lon):.6f})",
        )

    if goal_coords is not None:
        _add_marker(
            m,
            float(goal_coords.lat),
            float(goal_coords.lon),
            "Điểm đến",
            "red",
            "flag",
            tooltip="Điểm đến",
            popup=f"<b>Điểm đến</b><br>({float(goal_coords.lat):.6f}, {float(goal_coords.lon):.6f})",
        )

    for i, point in enumerate(route_points):
        is_start = point["stop_id"] == str(start_id)
        is_goal = point["stop_id"] == str(goal_id)

        if is_start:
            color = "green"
            icon = "play"
            label = "Bến gần điểm đi"
        elif is_goal:
            color = "red"
            icon = "flag"
            label = "Bến gần điểm đến"
        else:
            color = "blue"
            icon = "circle"
            label = f"Chặng {point['step']}"

        popup_html = f"""
        <b>{label}</b><br>
        <b>Bến:</b> {point["stop_name"]}<br>
        <b>Tuyến:</b> {point["route"]}<br>
        <b>ID:</b> {point["stop_id"]}<br>
        <b>Tọa độ:</b> ({point["lat"]:.6f}, {point["lon"]:.6f})
        """
        _add_marker(
            m,
            point["lat"],
            point["lon"],
            label,
            color,
            icon,
            tooltip=f"{point['stop_name']} · Tuyến {point['route']}",
            popup=popup_html,
        )

    m.fit_bounds(route_line, padding=(30, 30))
    return m
