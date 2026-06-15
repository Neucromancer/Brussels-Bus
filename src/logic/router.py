import heapq
import time
from logic.models import AStarNode
from logic.helpers import haversine, dist_to_minutes, reconstruct_path, find_nearest_stops
from data_engine.data_process import get_waiting_time
from const import WALKING_SPEED, BIRD_SPEED, UPPER_BOUND_FACTOR

def a_star_search(user_coords, dest_coords, all_stops):

    start_time = time.time() # Bắt đầu bấm giờ
    nodes_visited = 0        # Biến đếm số node đã lấy ra khỏi hàng đợi
    nodes_enqueued = 0       # Biến đếm số node được đẩy vào hàng đợi
    
    # === I. Khởi tạo hàng đợi ưu tiên và visited ===

    queue = []                                                                                                          
    visited = {}                                                                                                        
    best_time = float('inf')                                                                                            
    results = []                                                                                                        

    start_stops = find_nearest_stops(user_lat=user_coords.lat, user_lon=user_coords.lon, 
                                    all_stops=all_stops, radius_km=1.2)                                                 
    goal_stops = find_nearest_stops(user_lat=dest_coords.lat, user_lon=dest_coords.lon, 
                                    all_stops=all_stops, radius_km=1.2)                                                 

    for s_stop in start_stops:                                                                                          

        d_walk = haversine(user_coords.lat, user_coords.lon, s_stop.lat, s_stop.lon)                              
        g_start = dist_to_minutes(d_walk, speed_kmh=WALKING_SPEED)                                                
        
        d_to_dest = haversine(s_stop.lat, s_stop.lon, dest_coords.lat, dest_coords.lon)                           
        f_start = g_start + dist_to_minutes(d_to_dest, speed_kmh=BIRD_SPEED)                                      
        
        start_node = AStarNode(stop=s_stop, parent=None, g=g_start, f=f_start, route_id=None)                                    
        heapq.heappush(queue, start_node)
        nodes_enqueued += 1
        
        # Khóa trạng thái visited bằng Tuple (stop.id, route_id)
        visited_key = (s_stop.id, None)
        visited[visited_key] = g_start                                                                              

    # === II. Vòng lặp chính của A* ===

    while queue:

        current_node = heapq.heappop(queue)    
        nodes_visited += 1                                                                                        

        # Ngưỡng tỉa nhánh UPPER_BOUND_FACTOR được giữ nguyên
        if best_time != float('inf') and current_node.f > best_time * UPPER_BOUND_FACTOR:                         
            break

        if current_node.stop in goal_stops:                                                                       

            d_to_dest = haversine(current_node.stop.lat, current_node.stop.lon,                                   
                                  dest_coords.lat, dest_coords.lon)
            final_walk_time = dist_to_minutes(d_to_dest, speed_kmh=WALKING_SPEED)                                 
            
            total_duration = current_node.g + final_walk_time                                                     
            
            results.append({                                                                                      
                'path': reconstruct_path(current_node),
                'duration': total_duration
            })
            
            if total_duration < best_time:                                                                        
                best_time = total_duration

        for info in current_node.stop.next_stops:                                                                 

            arrival_time = current_node.g + info.travel_time                                                      
            
            if current_node.route_id and info.route_id != current_node.route_id:                                    
                arrival_time += get_waiting_time(info.route_id)

            h_score = dist_to_minutes(                                                                            
                haversine(info.stop.lat, info.stop.lon, dest_coords.lat, dest_coords.lon),
                speed_kmh=BIRD_SPEED 
            )

            # Khóa trạng thái bao gồm cả stop.id và route_id
            state_key = (info.stop.id, info.route_id)

            if state_key not in visited or arrival_time < visited[state_key]:                                 
                visited[state_key] = arrival_time
            
                new_node = AStarNode(                                                                             
                    stop=info.stop,
                    parent=current_node,
                    g=arrival_time,
                    f=arrival_time + h_score,
                    route_id=info.route_id 
                )
                heapq.heappush(queue, new_node)
                nodes_enqueued += 1
                
    # === III. KẾT THÚC VÀ LỌC ĐA DẠNG LỘ TRÌNH (ROUTE DIVERSITY FILTER) ===
    execution_time = time.time() - start_time
    
    for res in results:
        res['execution_time'] = execution_time
        res['nodes_visited'] = nodes_visited
        res['nodes_enqueued'] = nodes_enqueued

    # Sắp xếp các kết quả ban đầu
    sorted_results = sorted(results, key=lambda x: x['duration'])

    def get_transit_sequence(path):
        """Lấy danh sách thứ tự các tuyến xe sử dụng (Bỏ qua đoạn đi bộ)"""
        seq = []
        for node in path:
            rid = getattr(node, 'route_id', None)
            if rid and rid not in ("---", "Walking"):
                if not seq or seq[-1] != rid:
                    seq.append(rid)
        return seq

    def get_stop_set(path):
        """Lấy tập hợp ID các bến xe đi qua"""
        return set(node.stop.id for node in path if node.stop)

    def filter_routes(results_to_filter, current_accepted, max_overlap_ratio):
        new_accepted = list(current_accepted)
        for res in results_to_filter:
            if res in new_accepted:
                continue
                
            path_current = res['path']
            seq_current = get_transit_sequence(path_current)
            stops_current = get_stop_set(path_current)

            is_too_similar = False
            for accepted in new_accepted:
                path_accepted = accepted['path']
                seq_accepted = get_transit_sequence(path_accepted)
                stops_accepted = get_stop_set(path_accepted)

                # Tiêu chí 1: Trùng lặp hoàn toàn chuỗi tuyến xe
                if seq_current == seq_accepted and len(seq_current) > 0:
                    is_too_similar = True
                    break

                # Tiêu chí 2: Trùng lặp bến xe vượt quá ngưỡng cho phép
                if stops_current and stops_accepted:
                    overlap = len(stops_current.intersection(stops_accepted))
                    min_len = min(len(stops_current), len(stops_accepted))
                    if min_len > 0 and (overlap / min_len) > max_overlap_ratio:
                        is_too_similar = True
                        break

            if not is_too_similar:
                new_accepted.append(res)
                
            if len(new_accepted) == 3:
                break
        return new_accepted

    # 1. MÀNG LỌC 1: Khắt khe (Độ khác biệt ít nhất 40% -> Trùng lặp tối đa 60%)
    diverse_results = [sorted_results[0]] if sorted_results else []
    diverse_results = filter_routes(sorted_results, diverse_results, max_overlap_ratio=0.60)

    # 2. MÀNG LỌC 2: Nới lỏng (Nếu không đủ 3 đường, cho phép trùng tối đa 85%)
    if len(diverse_results) < 3:
        diverse_results = filter_routes(sorted_results, diverse_results, max_overlap_ratio=0.85)

    # 3. VÉT CẠN (Trường hợp mạng lưới quá ít đường đi thay thế)
    if len(diverse_results) < 3:
        for res in sorted_results:
            if res not in diverse_results:
                diverse_results.append(res)
            if len(diverse_results) == 3:
                break

    return sorted(diverse_results, key=lambda x: x['duration'])