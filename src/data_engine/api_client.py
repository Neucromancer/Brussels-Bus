import os
import requests

def download_static_data():
    # 1. Thông tin API và Header

    api_url = "https://api-management-opendata-production.azure-api.net/api/gtfs/feed/stibmivb/static/" 

    headers = {"bmc-partner-key": "1ada3c80c34e446794790ed2652acf3c"}

    # 2. Xác định vị trí lưu file tự động

    current_dir = os.path.dirname(os.path.abspath(__file__))                     # \Brussels Bus\src\data_engine
    src_dir = os.path.dirname(current_dir)                                       # \Brussels Bus\src
    base_dir = os.path.dirname(src_dir)                                          # \BRUSSELS-BUS
    data_dir = os.path.join(base_dir, "data")                                    # \BRUSSELS-BUS\data (nơi lưu file zip và database)
    os.makedirs(data_dir, exist_ok=True)                                         # Tự động tạo thư mục data nếu chưa có
    zip_file_path = os.path.join(data_dir, "brussels_gtfs.zip")                  # \BRUSSELS-BUS\data\brussels_gtfs.zip (nơi lưu file zip sau khi tải về)

    # 3. Tiến hành gọi API và tải file
    print(f"Đang tiến hành tải dữ liệu GTFS từ máy chủ Azure...")
    try:
   
        response = requests.get(api_url, headers=headers, stream=True)          # Gửi yêu cầu GET đến API với header chứa API key, và stream=True để tải file lớn
        
        response.raise_for_status()                                             # Nếu API trả về lỗi (4xx hoặc 5xx), sẽ ném ra exception và dừng chương trình
        
        with open(zip_file_path, 'wb') as f:                                    # Mở file zip để ghi dữ liệu
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Tải thành công! File đã được lưu an toàn tại:\n{zip_file_path}")
        
    except requests.exceptions.HTTPError as err:
        print(f"Lỗi xác thực hoặc API từ chối: {err}")
    except requests.exceptions.RequestException as e:
        print(f"Lỗi kết nối mạng: {e}")