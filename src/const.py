# I. Các hằng số dùng chung trong thuật toán A* và các phần khác của logic
WALKING_SPEED = 4                  # km/h
BIRD_SPEED = 25                    # km/h
METRO_SPEED = 25                   # km/h
BUS_SPEED = 15                     # km/h
TRANSFER_PENALTY_METRO = 4         # phút
TRANSFER_PENALTY_BUS = 10          # phút
UPPER_BOUND_FACTOR = 1.2           # Ngưỡng tỉa nhánh
METRO_LINES = {'1', '2', '5', '6'} # Các tuyến metro 

# II. Đường dẫn thư mục và file 
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
SRC_DIR = BASE_DIR / "src"
TESTS_DIR = BASE_DIR / "tests"

ZIP_PATH = DATA_DIR / "stib_database.zip"
EXTRACT_DIR = DATA_DIR / "gtfs_raw"
DB_PATH = DATA_DIR / "stib_database.db"
