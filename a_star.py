import heapq
from core.routing_utils import get_next_departure
from core.heuristic import heuristic


def a_star(graph, start, goal, coordinates, start_time):
    open_set = []
    heapq.heappush(open_set, (0, start))

    g_score = {start: 0}
    came_from = {}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            return reconstruct_path(came_from, current)

        for neighbor, dep_time in graph.get(current, []):
            next_dep = get_next_departure(start_time, dep_time)
            if next_dep is None:
                continue

            tentative_g = g_score[current] + (next_dep - start_time)

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current

                f = tentative_g + heuristic(coordinates[current], coordinates[neighbor])
                heapq.heappush(open_set, (f, neighbor))

    return None


def reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    return path[::-1]