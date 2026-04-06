import os
import requests
from dotenv import load_dotenv

def download_static_data():
    # 1. Tải các biến môi trường từ file .env lên hệ thống
    # Tìm file .env ở thư mục gốc và load nó
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(current_dir))
    dotenv_path = os.path.join(base_dir, '.env')
    
    load_dotenv(dotenv_path)

    # 2. Lấy API Key ra bằng os.getenv
    api_key = os.getenv("AZURE_STIB_API_KEY")
    
    # Kiểm tra bảo mật cơ bản: Nếu quên tạo file .env hoặc quên đặt tên biến
    if not api_key:
        raise ValueError("❌ Lỗi Bảo Mật: Không tìm thấy AZURE_STIB_API_KEY trong file .env!")

    # 3. Nạp Key vào Header
    api_url = "https://api-management-opendata-production.azure-api.net/api/gtfs/feed/stibmivb/static/" 
    headers = {
        "bmc-partner-key": api_key
    }

    # 4. Xác định vị trí lưu file (giữ nguyên như cũ)
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True) 
    zip_file_path = os.path.join(data_dir, "brussels_gtfs.zip")

    # 5. Tiến hành gọi API
    print(f"Đang tiến hành tải dữ liệu GTFS từ máy chủ Azure...")
    try:
        response = requests.get(api_url, headers=headers, stream=True)
        response.raise_for_status() 
        
        with open(zip_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"✅ Tải thành công! File đã được lưu an toàn tại:\n{zip_file_path}")
        
    except requests.exceptions.HTTPError as err:
        print(f"❌ Lỗi xác thực hoặc API từ chối: {err}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi kết nối mạng: {e}")

if __name__ == "__main__":
    download_static_data()