import heapq
import sqlite3
import os
from logic.models import AStarNode
from logic.helpers import haversine, dist_to_minutes, reconstruct_path, find_nearest_stops
from data_engine.data_process import get_waiting_time
from const import WALKING_SPEED, BIRD_SPEED, UPPER_BOUND_FACTOR

def a_star_search(user_coords, dest_coords, all_stops):

    # === I. Khởi tạo hàng đợi ưu tiên và visited, truyền vào 3 node đầu tiên ===

    queue = []                                                                                                  # Khởi tạo hàng đợi ưu tiên (Min-Heap)
    visited = {}                                                                                                # {stop_id: g_cost} - Lưu chi phí thực tế thấp nhất đã đạt được đến bến này để tỉa nhánh
    best_time = float('inf')                                                                                    # Biến lưu thời gian tốt nhất tìm được đến giờ để áp dụng ngưỡng tỉa nhánh
    results = []                                                                                                # Danh sách lưu các đường đi tìm được đến các bến đích

    start_stops = find_nearest_stops(user_lat=user_coords.lat, user_lon=user_coords.lon, 
                                     all_stops=all_stops, radius_km=1.2)                                          # Tìm 3 bến gần nhất với điểm bắt đầu
    goal_stops = find_nearest_stops(user_lat=dest_coords.lat, user_lon=dest_coords.lon, 
                                    all_stops=all_stops, radius_km=1.2)                                          # Tìm 3 bến gần nhất với điểm đích

    for s_stop in start_stops:                                                                                  # Nạp 3 bến xuất phát vào Queue (Tính kèm thời gian đi bộ)

        d_walk = haversine(user_coords.lat, user_coords.lon, s_stop.lat, s_stop.lon)                              # Khoảng cách đi bộ từ điểm bắt đầu đến bến
        g_start = dist_to_minutes(d_walk, speed_kmh=WALKING_SPEED)                                                # Ước lượng thời gian đi bộ
        
        d_to_dest = haversine(s_stop.lat, s_stop.lon, dest_coords.lat, dest_coords.lon)                           # Khoảng cách từ bến hiện tại này đến đích
        f_start = g_start + dist_to_minutes(d_to_dest, speed_kmh=BIRD_SPEED)                                      # Ước lượng thời gian vận tốc chim bay từ bến này đến đích (Heuristic)
        
        start_node = AStarNode(stop=s_stop, parent=None, g=g_start, f=f_start)                                    # Tạo Node khởi đầu đưa vào hàng đợi ưu tiên
        heapq.heappush(queue, start_node)
        
        visited[s_stop.id] = g_start                                                                              # Đánh dấu đã ghé qua bến với chi phí thực tế

    # === II. Vòng lặp chính của A* ===

    while queue:

        current_node = heapq.heappop(queue)                                                                     # 1. LẤY NODE CÓ f(x) NHỎ NHẤT RA KHỎI HÀNG ĐỢI ĐỂ XỬ LÍ

        if best_time != float('inf') and current_node.f > best_time * UPPER_BOUND_FACTOR:                         # 2. Thực hiện cắt tỉa nếu chi phí vượt UPPER_BOUND_FACTOR lần chi phí tốt nhất
            break

        if current_node.stop in goal_stops:                                                                     # 3. KIỂM TRA HIỆN TẠI CÓ PHẢI NODE ĐÍCH (Goal Check) VÀ LƯU DANH SÁCH KẾT QUẢ

            d_to_dest = haversine(current_node.stop.lat, current_node.stop.lon,                                     # Ước lượng khoảng cách từ bến hiện tại đến đích
                                  dest_coords.lat, dest_coords.lon)
            final_walk_time = dist_to_minutes(d_to_dest, speed_kmh=WALKING_SPEED)                                 # Thời gian đi bộ ước lượng từ bến cuối này đến đích
            
            total_duration = current_node.g + final_walk_time                                                       # Cập nhật g(x)
            
            results.append({                                                                                        # Lưu kết quả đạt được vào danh sách results[]
                'path': reconstruct_path(current_node),
                'duration': total_duration
            })
            
            if total_duration < best_time:                                                                          # Cập nhật thời gian tốt nhất nếu đường đi này nhanh hơn
                best_time = total_duration

        for info in current_node.stop.next_stops:                                                               # 4. DUYỆT CÁC BẾN KẾ TIẾP (Neighbors)

            arrival_time = current_node.g + info.travel_time                                                        # a. Tính g(x) mới = g cũ + thời gian di chuyển bus
            
            if current_node.route_id and info.route_id != current_node.route_id:                                    # b. Tính phí chuyển tuyến (Transfer Penalty) nếu có sự thay đổi tuyến xe
                arrival_time += get_waiting_time(info.route_id)

            h_score = dist_to_minutes(                                                                              # c. Tính h(x) mới = Ước lượng thời gian từ bến kế tiếp đến đích (dùng khoảng cách chim bay)
                haversine(info.stop.lat, info.stop.lon, dest_coords.lat, dest_coords.lon),
                speed_kmh=BIRD_SPEED 
            )

            if info.stop.id not in visited or arrival_time < visited[info.stop.id]:                                 # d. Thực hiện tỉa nếu lặp lại một bến với thời gian tồi hơn
                visited[info.stop.id] = arrival_time
            
                new_node = AStarNode(                                                                               # Nếu không bị tỉa, tạo Node đưa vào hàng đợi
                    stop=info.stop,
                    parent=current_node,
                    g=arrival_time,
                    f=arrival_time + h_score,
                    route_id=info.route_id # Lưu lại để kiểm tra chuyển tuyến ở bước sau
                )
                heapq.heappush(queue, new_node)

    return sorted(results, key=lambda x:    x['duration'])                                                      # Trả về list các đường từ nhanh đến chậm                    


# === III. HÀM MỚI: XỬ LÝ HÌNH HỌC ĐƯỜNG CONG ===

def get_curved_segment(route_id, lat_A, lon_A, lat_B, lon_B, db_path=None):
    """
    Truy vấn Database để lấy mảng tọa độ uốn lượn thực tế.
    Phiên bản Ultimate: Tự động phát hiện đúng chiều đi (Outbound/Inbound).
    """
    if db_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(base_dir, "data", "stib_database.db")
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Lấy TẤT CẢ các shape_id của tuyến xe này (bao gồm cả lượt đi và về)
        # Ép kiểu CAST sang TEXT để tránh lỗi khác biệt dữ liệu int/string
        cursor.execute("""
            SELECT DISTINCT t.shape_id 
            FROM trips t
            JOIN routes r ON t.route_id = r.route_id
            WHERE CAST(r.route_short_name AS TEXT) = ? 
        """, (str(route_id),))
        
        shape_ids = [row[0] for row in cursor.fetchall() if row[0]]
        
        if not shape_ids:
            conn.close()
            print(f"Cảnh báo: Không tìm thấy dây hình học cho tuyến {route_id}.")
            return [(lat_A, lon_A), (lat_B, lon_B)]

        def find_nearest_idx_and_dist(target_lat, target_lon, pts):
            min_dist = float('inf')
            best_idx = 0
            for i, (p_lat, p_lon) in enumerate(pts):
                dist = (target_lat - p_lat)**2 + (target_lon - p_lon)**2
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
            return best_idx, min_dist

        best_segment = [(lat_A, lon_A), (lat_B, lon_B)]
        min_total_dist = float('inf')

        # 2. Duyệt qua từng sợi dây để tìm ra sợi khớp nhất với bến A và B
        for sid in shape_ids:
            cursor.execute("""
                SELECT shape_pt_lat, shape_pt_lon 
                FROM shapes 
                WHERE shape_id = ? 
                ORDER BY shape_pt_sequence
            """, (sid,))
            shape_pts = cursor.fetchall()

            if not shape_pts: continue

            idx_A, dist_A = find_nearest_idx_and_dist(lat_A, lon_A, shape_pts)
            idx_B, dist_B = find_nearest_idx_and_dist(lat_B, lon_B, shape_pts)
            
            total_dist = dist_A + dist_B

            # 3. Chọn sợi dây có tổng khoảng cách tới 2 bến là nhỏ nhất (Đúng chiều nhất)
            if total_dist < min_total_dist:
                min_total_dist = total_dist
                
                # Chốt chặn an toàn: Ngưỡng 0.0003 (~600m). 
                if idx_A != idx_B and dist_A < 0.0003 and dist_B < 0.0003:
                    if idx_A < idx_B:
                        segment = shape_pts[idx_A : idx_B + 1]
                    else:
                        segment = shape_pts[idx_B : idx_A + 1][::-1]
                        
                    best_segment = [(lat_A, lon_A)] + segment + [(lat_B, lon_B)]

        conn.close()
        return best_segment
        
    except Exception as e:
        print(f"Lỗi truy xuất đường cong DB (Tuyến {route_id}): {e}")
        return [(lat_A, lon_A), (lat_B, lon_B)]