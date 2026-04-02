import heapq
from core.routing_utils import get_next_departure
from core.heuristic import heuristic
from utils.time_utils import time_to_seconds


def a_star(graph, start, goal, coordinates, start_time):
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    start_seconds = time_to_seconds(start_time)
    g_score = {start: start_seconds}
    visited = set()
    came_from = {}
    
    if start == goal:
        return [start]
    
    while open_set:
        f_score, current = heapq.heappop(open_set)
        
        # ✅ CRITICAL: Skip if already visited
        if current in visited:
            continue
        visited.add(current)
        
        if current == goal:
            return reconstruct_path(came_from, current)
        
        current_time = g_score[current]
        
        for neighbor, dep_time, arrival_time in graph.get(current, []):
            if neighbor in visited:  # ✅ Skip visited neighbors
                continue
            
            next_dep = get_next_departure(current_time, dep_time)
            if next_dep is None:
                continue
            
            arrival_seconds = time_to_seconds(arrival_time)
            tentative_g = arrival_seconds
            
            # Only add if it's a better path
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                
                f = tentative_g + heuristic(coordinates[neighbor], coordinates[goal])
                heapq.heappush(open_set, (f, neighbor))
    
    return None

def reconstruct_path(came_from, current, max_depth=10000):
    path = [current]
    depth = 0
    
    while current in came_from and depth < max_depth:
        current = came_from[current]
        path.append(current)
        depth += 1
    
    if depth >= max_depth:
        raise RuntimeError(f"Cycle detected in came_from at depth {max_depth}. Path so far: {path}")
    
    return path[::-1]
