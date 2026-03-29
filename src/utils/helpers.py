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