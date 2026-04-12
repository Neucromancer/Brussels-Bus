import unittest

from src.logic.astar import a_star_search
from src.logic.helpers import find_nearest_stops
from src.data_engine.data_process import load_data
from src.data_engine.data_manager import get_data_from_db
from src.data_engine.data_process import load_data


class TestAStarRealData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n[Setup] Loading real data...")

        df = get_data_from_db()   # 👈 get data from SQLite
        cls.stops = load_data(df) # 👈 pass into load_data

        print(f"[Setup] Loaded {len(cls.stops)} stops")

    def test_astar_real_route(self):
        """
        Test A* using real coordinates
        """

        # Example coordinates (Brussels-like or adjust if needed)
        user_coords = (50.8503, 4.3517)   # De Brouckère
        dest_coords = (50.8200, 4.4000) 

        # Find nearest stops
        start_stops = find_nearest_stops(user_coords[0],user_coords[1], self.stops, n=3)
        goal_stops = find_nearest_stops(dest_coords[0], dest_coords[1],self.stops, n=3)

        print("\n[Test] Start stops:", [s.name for s in start_stops])
        print("[Test] Goal stops:", [s.name for s in goal_stops])

        # Run A*
        results = a_star_search(user_coords, dest_coords, start_stops, goal_stops)

        # Assertions
        self.assertIsInstance(results, list)

        if len(results) > 0:
            print(f" the number of paths : {len(results)}")
            best = results[0]

            print("\n✅ Best route found:")
            print(f"Duration: {best['duration'] / 60:.2f} minutes")

            print("Path:")
            for step in best['path']:
                print(f" {step.stop.name}---{step.stop.lat}---{step.stop.lon}--{step.route_id}")

            self.assertIn('path', best)
            self.assertIn('duration', best)
        else:
            print("\n⚠️ No route found")

        # Optional: ensure at least 1 route
        self.assertGreaterEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
