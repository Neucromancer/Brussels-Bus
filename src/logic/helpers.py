from math import radians, cos, sin, asin, sqrt

# === Các hàm tiện ích ===

def haversine(lat1, lon1, lat2, lon2):
    # Chuyển đổi độ sang radian
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Công thức Haversine
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Bán kính Trái Đất tính theo km
    return c * r

def dist_to_minutes(distance_km, speed_kmh=20):
    return (distance_km / speed_kmh) * 60

def walking_time(distance_km, speed_kmh=3.6):
    return (distance_km / speed_kmh) * 60

def find_nearest_stop(user_lat, user_lon, all_stops):
    # Trả về stop_id của bến có khoảng cách haversine nhỏ nhất
    return min(all_stops, key=lambda s: haversine(user_lat, user_lon, s.lat, s.lon))

def find_nearest_stops(user_lat, user_lon, all_stops, n=3):
    # Trả về danh sách n bến gần nhất
    sorted_stops = sorted(all_stops, key=lambda s: haversine(user_lat, user_lon, s.lat, s.lon))
    return sorted_stops[:n]

def reconstruct_path(node):
    # Đi ngược từ node đích về node gốc để xây dựng lại đường đi
    path = []
    while node:
        path.append((node.stop.name, node.route.id if node.route else None))
        node = node.parent
    return path[::-1] # Đảo ngược để có thứ tự từ gốc đến đích