import sqlite3
from scipy.spatial import KDTree

class NearestStopFinder:
    def __init__(self, db_path, valid_stop_ids=None):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        if valid_stop_ids:
            placeholders = ",".join(["?"] * len(valid_stop_ids))
            query = f"SELECT stop_id, stop_lat, stop_lon FROM stops WHERE stop_id IN ({placeholders})"
            cur.execute(query, list(valid_stop_ids))
        else:
            cur.execute("SELECT stop_id, stop_lat, stop_lon FROM stops")

        data = cur.fetchall()
        conn.close()

        self.ids = [row[0] for row in data]
        self.coords = [(row[1], row[2]) for row in data]
        self.tree = KDTree(self.coords)

    def find(self, lat, lon):
        _, idx = self.tree.query((lat, lon))
        return self.ids[idx]