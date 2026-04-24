import heapq
from logic.models import AStarNode
from logic.helpers import haversine, dist_to_minutes, reconstruct_path, find_nearest_stops
from data_engine.data_process import get_waiting_time
from const import WALKING_SPEED, BIRD_SPEED, UPPER_BOUND_FACTOR

def a_star_search(user_coords, dest_coords, all_stops):

    # === I. Khởi tạo hàng đợi ưu tiên và visited, truyền vào 3 node đầu tiên ===

    queue = []                                                                                                    # Khởi tạo hàng đợi ưu tiên (Min-Heap)
    visited = {}                                                                                                  # {stop_id: g_cost} - Lưu chi phí thực tế thấp nhất đã đạt được đến bến này để tỉa nhánh
    best_time = float('inf')                                                                                      # Biến lưu thời gian tốt nhất tìm được đến giờ để áp dụng ngưỡng tỉa nhánh
    results = []                                                                                                  # Danh sách lưu các đường đi tìm được đến các bến đích

    start_stops = find_nearest_stops(user_lat=user_coords.lat, user_lon=user_coords.lon, 
                                    all_stops=all_stops, radius_km=1.2)                                           # Tìm 3 bến gần nhất với điểm bắt đầu
    goal_stops = find_nearest_stops(user_lat=dest_coords.lat, user_lon=dest_coords.lon, 
                                    all_stops=all_stops, radius_km=1.2)                                           # Tìm 3 bến gần nhất với điểm đích

    for s_stop in start_stops:                                                                                    # Nạp 3 bến xuất phát vào Queue (Tính kèm thời gian đi bộ)

        d_walk = haversine(user_coords.lat, user_coords.lon, s_stop.lat, s_stop.lon)                              # Khoảng cách đi bộ từ điểm bắt đầu đến bến
        g_start = dist_to_minutes(d_walk, speed_kmh=WALKING_SPEED)                                                # Ước lượng thời gian đi bộ
        
        d_to_dest = haversine(s_stop.lat, s_stop.lon, dest_coords.lat, dest_coords.lon)                           # Khoảng cách từ bến hiện tại này đến đích
        f_start = g_start + dist_to_minutes(d_to_dest, speed_kmh=BIRD_SPEED)                                      # Ước lượng thời gian vận tốc chim bay từ bến này đến đích (Heuristic)
        
        start_node = AStarNode(stop=s_stop, parent=None, g=g_start, f=f_start)                                    # Tạo Node khởi đầu đưa vào hàng đợi ưu tiên
        heapq.heappush(queue, start_node)
        
        visited[s_stop.id] = g_start                                                                              # Đánh dấu đã ghé qua bến với chi phí thực tế

    # === II. Vòng lặp chính của A* ===

    while queue:

        current_node = heapq.heappop(queue)                                                                       # 1. LẤY NODE CÓ f(x) NHỎ NHẤT RA KHỎI HÀNG ĐỢI ĐỂ XỬ LÍ

        if best_time != float('inf') and current_node.f > best_time * UPPER_BOUND_FACTOR:                         # 2. Thực hiện cắt tỉa nếu chi phí vượt UPPER_BOUND_FACTOR lần chi phí tốt nhất
            break

        if current_node.stop in goal_stops:                                                                       # 3. KIỂM TRA HIỆN TẠI CÓ PHẢI NODE ĐÍCH (Goal Check) VÀ LƯU DANH SÁCH KẾT QUẢ

            d_to_dest = haversine(current_node.stop.lat, current_node.stop.lon,                                     # Ước lượng khoảng cách từ bến hiện tại đến đích
                                  dest_coords.lat, dest_coords.lon)
            final_walk_time = dist_to_minutes(d_to_dest, speed_kmh=WALKING_SPEED)                                   # Thời gian đi bộ ước lượng từ bến cuối này đến đích
            
            total_duration = current_node.g + final_walk_time                                                       # Cập nhật g(x)
            
            results.append({                                                                                        # Lưu kết quả đạt được vào danh sách results[]
                'path': reconstruct_path(current_node),
                'duration': total_duration
            })
            
            if total_duration < best_time:                                                                        # Cập nhật thời gian tốt nhất nếu đường đi này nhanh hơn
                best_time = total_duration

        for info in current_node.stop.next_stops:                                                                 # 4. DUYỆT CÁC BẾN KẾ TIẾP (Neighbors)

            arrival_time = current_node.g + info.travel_time                                                        # a. Tính g(x) mới = g cũ + thời gian di chuyển bus
            
            if current_node.route_id and info.route_id != current_node.route_id:                                    # b. Tính phí chuyển tuyến (Transfer Penalty) nếu có sự thay đổi tuyến xe
                arrival_time += get_waiting_time(info.route_id)

            h_score = dist_to_minutes(                                                                              # c. Tính h(x) mới = Ước lượng thời gian từ bến kế tiếp đến đích (dùng khoảng cách chim bay)
                haversine(info.stop.lat, info.stop.lon, dest_coords.lat, dest_coords.lon),
                speed_kmh=BIRD_SPEED 
            )

            if info.stop.id not in visited or arrival_time < visited[info.stop.id]:                                 # d. Thực hiện tỉa nếu lặp lại một bến với thời gian tồi hơn
                visited[info.stop.id] = arrival_time
            
                new_node = AStarNode(                                                                                 # Nếu không bị tỉa, tạo Node đưa vào hàng đợi
                    stop=info.stop,
                    parent=current_node,
                    g=arrival_time,
                    f=arrival_time + h_score,
                    route_id=info.route_id # Lưu lại để kiểm tra chuyển tuyến ở bước sau
                )
                heapq.heappush(queue, new_node)

    return sorted(results, key=lambda x:    x['duration'])                                                      # Trả về list các đường từ nhanh đến chậm                    