import time
from core.data_loader import load_stop_times, load_coordinates_for_used_stops
from core.graph_builder import build_graph
from core.a_star import a_star
from utils.nearest_stop import NearestStopFinder
DB_PATH = "data/stib_database.db"

print("Loading data...")
start_load = time.time()

stop_times = load_stop_times(DB_PATH)
graph = build_graph(stop_times)
coordinates = load_coordinates_for_used_stops(DB_PATH, stop_times)

print("Data loaded in", round(time.time() - start_load, 2), "seconds")


finder = NearestStopFinder(DB_PATH, valid_stop_ids=set(coordinates.keys()))

# 🔥 Put ANY coordinates you want here
start_lat, start_lon = 50.8416, 4.3505
goal_lat, goal_lon = 50.8532, 4.3536

start = finder.find(start_lat, start_lon)
goal = finder.find(goal_lat, goal_lon)



print("\nStart:", start)
print("Goal:", goal)

# Check data consistency
print("\nChecking data...")
print("Start in graph:", start in graph)
print("Goal in graph:", goal in graph)
print("Start in coordinates:", start in coordinates)
print("Goal in coordinates:", goal in coordinates)

# Run A*
print("\nRunning A*...")
start_time_exec = time.time()

path = a_star(graph, start, goal, coordinates, start_time=0)

end_time_exec = time.time()

# Show result
print("\nResult:")
if path:
    print("Path found!")
    print("Length:", len(path))
    print("Path sample:", path[:10])
else:
    print("No path found")

print("Execution time:", round(end_time_exec - start_time_exec, 4), "seconds")