import heapq
from logic.models import AStarNode
from logic.helpers import haversine, dist_to_minutes, reconstruct_path, find_nearest_stops
from data_engine.data_process import get_waiting_time

def a_star_search(user_coords, dest_coords, all_stops):
    """
    user_coords: truyền vào tupple (lat, lon) của người dùng
    start_stops: Danh sách 3 bến gần người dùng nhất
    goal_stops: Danh sách 3 bến gần đích nhất
    """
    # === I. Khởi tạo hàng đợi ưu tiên và visited, truyền vào 3 node đầu tiên ===

    # 1. Khởi tạo hàng đợi ưu tiên (Min-Heap)
    queue = []
    
    # 2. Từ điển lưu chi phí g thấp nhất từng đạt được tới mỗi bến
    # Cấu trúc: {stop_id: min_g}
    visited = {} 

    start_stops = find_nearest_stops(user_lat=user_coords.lat, user_lon=user_coords.lon, all_stops=all_stops, n=3) # Tìm 3 bến gần nhất với người dùng
    goal_stops = find_nearest_stops(user_lat=dest_coords.lat, user_lon=dest_coords.lon, all_stops=all_stops, n=3) #

    # 3. Nạp 3 bến xuất phát vào Queue (Tính kèm thời gian đi bộ)
    for s_stop in start_stops:
        # Khoảng cách đi bộ từ chỗ đứng đến bến
        d_walk = haversine(user_coords.lat, user_coords.lon, s_stop.lat, s_stop.lon)
        g_start = dist_to_minutes(d_walk, speed_kmh=4) # Đi bộ 4km/h
        
        # Heuristic: Từ bến này chim bay đến Tọa độ đích thực tế (25km/h)
        d_to_dest = haversine(s_stop.lat, s_stop.lon, dest_coords.lat, dest_coords.lon)
        f_start = g_start + dist_to_minutes(d_to_dest, speed_kmh=25)
        
        # Tạo Node và đẩy vào Hàng đợi ưu tiên
        start_node = AStarNode(stop=s_stop, parent=None, g=g_start, f=f_start)
        heapq.heappush(queue, start_node)
        
        # Đánh dấu đã ghé thăm bến này với chi phí g_start
        visited[s_stop.id] = g_start

    # === II. Vòng lặp chính của A* ===

    best_time = float('inf') # Biến lưu thời gian tốt nhất tìm được đến giờ để áp dụng ngưỡng tỉa nhánh
    results = []             # Danh sách lưu các đường đi tìm được đến các bến đích

    while queue:
        # 1. LẤY NODE CÓ f(x) NHỎ NHẤT RA KHỎI HÀNG ĐỢI ĐỂ XỬ LÍ
        current_node = heapq.heappop(queue)

        # 2. KIỂM TRA NGƯỠNG TỐI ƯU (1.15x)

        # Nếu chi phí dự kiến đã vượt quá 115% đường tốt nhất tìm thấy -> Dừng duyệt
        if best_time != float('inf') and current_node.f > best_time * 1.15:
            break

        # 3. KIỂM TRA HIỆN TẠI CÓ PHẢI NODE ĐÍCH (Goal Check) VÀ LƯU DANH SÁCH KẾT QUẢ
        if current_node.stop in goal_stops:
            # Tính thời gian đi bộ từ bến này về tọa độ đích thực tế
            d_to_dest = haversine(current_node.stop.lat, current_node.stop.lon, 
                                  dest_coords.lat, dest_coords.lon)
            final_walk_time = dist_to_minutes(d_to_dest, speed_kmh=4)
            
            total_duration = current_node.g + final_walk_time
            
            # Lưu lại kết quả và cập nhật best_time
            results.append({
                'path': reconstruct_path(current_node),
                'duration': total_duration
            })
            
            if total_duration < best_time:
                best_time = total_duration

        # 4. DUYỆT CÁC BẾN KẾ TIẾP (Neighbors)

        for info in current_node.stop.next_stops: # Duyệt từng bến kế tiếp

            # a. Tính g(x) mới = g cũ + thời gian di chuyển bus
            arrival_time = current_node.g + info.travel_time
            
            # b. Tính phí chuyển tuyến (Transfer Penalty) nếu có sự thay đổi tuyến xe
            if current_node.route_id and info.route_id != current_node.route_id:
                # get_waiting_time lấy từ db_manager hoặc config
                arrival_time += get_waiting_time(info.route_id)

            # c. Tính Heuristic h(x) - Chim bay từ bến này đến Đích thực tế
            h_score = dist_to_minutes(
                haversine(info.stop.lat, info.stop.lon, dest_coords.lat, dest_coords.lon),
                speed_kmh=25 # Vận tốc bus trung bình
            )

            # d. Tỉa nhánh nếu đi lặp lại một bến (Pruning)
            if info.stop.id not in visited or arrival_time < visited[info.stop.id]:
                visited[info.stop.id] = arrival_time
            
            # e. Sau khi lọc node, tính toán và cắt tỉa => Tạo Node mới và đẩy vào hàng đợi
                new_node = AStarNode(
                    stop=info.stop,
                    parent=current_node,
                    g=arrival_time,
                    f=arrival_time + h_score,
                    route_id=info.route_id # Lưu lại để kiểm tra chuyển tuyến ở bước sau
                )
                heapq.heappush(queue, new_node)

    return sorted(results, key=lambda x:    x['duration']) # Trả về list các đường từ nhanh đến chậm

