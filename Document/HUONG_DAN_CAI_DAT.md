# 📱 Hướng Dẫn Cài Đặt & Chạy Project LTGIS - Web Bán Điện Thoại

> **Công nghệ:** Django 6.0 + PostgreSQL + PostGIS + GDAL (OSGeo4W)
> **Hệ điều hành:** Windows

---

## Mục Lục

1. [Yêu Cầu Hệ Thống](#1-yêu-cầu-hệ-thống)
2. [Cài Đặt Phần Mềm Tiên Quyết](#2-cài-đặt-phần-mềm-tiên-quyết)
3. [Cấu Hình Database](#3-cấu-hình-database)
4. [Cài Đặt Python & Thư Viện](#4-cài-đặt-python--thư-viện)
5. [Chạy Project](#5-chạy-project)
6. [Các URL Chính](#6-các-url-chính)
7. [Xử Lý Lỗi Thường Gặp](#7-xử-lý-lỗi-thường-gặp)
8. [Video Hướng Dẫn & Báo Cáo](#8-video-hướng-dẫn--báo-cáo)
---

## 1. Yêu Cầu Hệ Thống

| Thành phần | Phiên bản yêu cầu | Ghi chú |
|---|---|---|
| **Python** | 3.12 trở lên | Django 6.0 yêu cầu Python ≥ 3.12 |
| **PostgreSQL** | 16 hoặc 18 | File dump được tạo từ PostgreSQL 18.1 |
| **PostGIS** | 3.x | Extension GIS cho PostgreSQL |
| **OSGeo4W** | Bản mới nhất | Cung cấp thư viện GDAL cho Django |
| **pip** | Bản mới nhất | Quản lý package Python |

---

## 2. Cài Đặt Phần Mềm Tiên Quyết

### 2.1. Cài Python 3.12+

1. Tải Python từ [python.org/downloads](https://www.python.org/downloads/)
2. Khi cài đặt, **bắt buộc tick ☑ "Add Python to PATH"**
3. Kiểm tra sau khi cài:

```powershell
python --version
# Kết quả mong đợi: Python 3.12.x hoặc cao hơn
```

### 2.2. Cài PostgreSQL

1. Tải PostgreSQL từ [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
2. Chạy installer, ghi nhớ **password** bạn đặt cho user `postgres`
3. Trong quá trình cài, chọn cài kèm **Stack Builder**
4. Sau khi cài xong, mở **Stack Builder** → chọn **Spatial Extensions** → cài **PostGIS**

> [!IMPORTANT]
> PostGIS là **BẮT BUỘC** vì project sử dụng tính năng bản đồ GIS (Store Locator).
> Nếu bạn không cài PostGIS, Django sẽ báo lỗi khi restore database.

### 2.3. Cài OSGeo4W (GDAL)

1. Tải OSGeo4W từ [trac.osgeo.org/osgeo4w](https://trac.osgeo.org/osgeo4w/)
2. Chạy installer → chọn **Express Install** → tick **GDAL**
3. Cài đặt vào đường dẫn mặc định: `C:\OSGeo4W`
4. Sau khi cài, kiểm tra file GDAL DLL:

```powershell
# Tìm file gdal*.dll trong thư mục bin
Get-ChildItem "C:\OSGeo4W\bin" -Filter "gdal*.dll" | Select-Object Name
```

> [!WARNING]
> Nếu tên file DLL KHÁC `gdal310.dll` (ví dụ `gdal309.dll` hoặc `gdal311.dll`),
> bạn cần sửa file `settings.py` cho khớp. Xem [Mục 7.2](#72-lỗi-gdal-library-not-found).

---

## 3. Cấu Hình Database

### 3.1. Tạo Database

Mở **pgAdmin 4** hoặc dùng command line `psql`:

```sql
-- Kết nối vào PostgreSQL
psql -U postgres

-- Tạo database
CREATE DATABASE bandienthoai_db2;

-- Kết nối vào database vừa tạo
\c bandienthoai_db2

-- Bật extension PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Thoát
\q
```

### 3.2. Import Dữ Liệu Mẫu

File `phone_store.sql` là file backup dạng **binary (custom format)** của PostgreSQL. Dùng lệnh `pg_restore`:

```powershell
# Chạy từ thư mục gốc của project
pg_restore -U postgres -d bandienthoai_db2 --no-owner --no-privileges "d:\dowload\LTGIS-dev\LTGIS-dev\phone_store.sql"
```

> Nhập password của user `postgres` khi được hỏi.

> [!TIP]
> Nếu gặp lỗi `pg_restore: command not found`, thêm đường dẫn PostgreSQL vào PATH:
> ```powershell
> $env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
> ```
> Hoặc chạy trực tiếp: `& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" ...`

### 3.3. Kiểm Tra Thông Tin Kết Nối

Mở file [settings.py](file:///d:/dowload/LTGIS-dev/LTGIS-dev/project-gis/webbanhang/settings.py#L82-L91) và đảm bảo thông tin khớp với PostgreSQL của bạn:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'bandienthoai_db2',    # Tên database
        'USER': 'postgres',             # Username
        'PASSWORD': '123456',           # ⚠️ Đổi thành password của bạn
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

> [!CAUTION]
> Nếu password PostgreSQL của bạn **KHÁC** `123456`, bạn **PHẢI** sửa lại giá trị `PASSWORD` trong file `settings.py`.

---

## 4. Cài Đặt Python & Thư Viện

### 4.1. Tạo Virtual Environment

```powershell
# Di chuyển vào thư mục project
cd "d:\dowload\LTGIS-dev\LTGIS-dev\project-gis"

# Tạo virtual environment
python -m venv venv

# Kích hoạt virtual environment
.\venv\Scripts\Activate.ps1
```

> [!WARNING]
> Nếu khi chạy lệnh tạo môi trường gặp lỗi **"Python was not found..."**, đó là do Windows Store alias đang chặn lệnh python. Bạn hãy làm theo cách sau:
> 1. Mở **Settings** của Windows → Tìm **"App execution aliases"**.
> 2. Tìm dòng `python.exe` và `python3.exe` (có icon App Installer) và **TẮT** (Off) chúng đi.
> 3. Tắt terminal hiện tại, mở terminal mới và chạy lại lệnh.
> *(Xem thêm [Mục 7.7](#77-lỗi-python-was-not-found-khi-tạo-venv) nếu vẫn lỗi)*

> [!NOTE]
> Nếu gặp lỗi `Activate.ps1 cannot be loaded because running scripts is disabled`,
> chạy lệnh sau trong PowerShell (quyền Admin):
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 4.2. Cài Đặt Các Thư Viện Python

```powershell
# Đảm bảo đang ở trong venv (thấy (venv) ở đầu dòng lệnh)

# Cài Django 6.0
pip install django==6.0.1

# Driver PostgreSQL
pip install psycopg2-binary

# Xử lý ảnh (upload sản phẩm, avatar...)
pip install Pillow

# Xuất/Nhập file Excel
pip install openpyxl

# AI Chat (tích hợp Groq)
pip install groq
```

Hoặc cài tất cả cùng lúc:

```powershell
pip install django==6.0.1 psycopg2-binary Pillow openpyxl groq
```

### 4.3. Danh Sách Đầy Đủ Các Package

| Package | Mục đích |
|---|---|
| `django==6.0.1` | Web framework chính |
| `psycopg2-binary` | Kết nối PostgreSQL |
| `Pillow` | Xử lý ảnh (ImageField) |
| `openpyxl` | Xuất/nhập file Excel (sản phẩm, đơn hàng) |
| `groq` | API chat AI tích hợp (Groq LLM) |

---

## 5. Chạy Project

### 5.1. Chạy Migration (nếu cần)

```powershell
cd "d:\dowload\LTGIS-dev\LTGIS-dev\project-gis"

# Kích hoạt venv (nếu chưa kích hoạt)
.\venv\Scripts\Activate.ps1

# Chạy migration
python manage.py migrate
```

> [!NOTE]
> Nếu bạn đã import dữ liệu từ `phone_store.sql` thành công, bước migrate có thể báo
> `No migrations to apply` — điều này là **bình thường**.

### 5.2. Khởi Động Server

```powershell
python manage.py runserver
```

Kết quả mong đợi:

```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
May 08, 2026 - 12:30:00
Django version 6.0.1, using settings 'webbanhang.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### 5.3. Truy Cập Website

Mở trình duyệt và truy cập:

🌐 **http://127.0.0.1:8000/**

---

## 6. Các URL Chính

### Trang Khách Hàng (Client)

| URL | Chức năng |
|---|---|
| `/` | Trang chủ |
| `/product/<id>/` | Chi tiết sản phẩm |
| `/cart/` | Giỏ hàng |
| `/checkout/` | Thanh toán |
| `/store-locator/` | Bản đồ tìm cửa hàng (GIS) |
| `/search/` | Tìm kiếm sản phẩm |
| `/login/` | Đăng nhập |
| `/register/` | Đăng ký |
| `/account/` | Thông tin tài khoản |
| `/my-orders/` | Lịch sử đơn hàng |
| `/tin-tuc/` | Tin tức |
| `/feedback/` | Gửi ý kiến khách hàng |

### Trang Quản Trị (Admin)

| URL | Chức năng |
|---|---|
| `/my-admin/` | Dashboard tổng quan |
| `/my-admin/products/` | Quản lý sản phẩm |
| `/my-admin/orders/` | Quản lý đơn hàng |
| `/my-admin/stock/` | Quản lý kho hàng |
| `/my-admin/stores/` | Quản lý cửa hàng |
| `/my-admin/regions/` | Quản lý khu vực |
| `/my-admin/transfers/` | Điều chuyển kho |
| `/my-admin/stocktaking/` | Kiểm kê kho |
| `/my-admin/employees/` | Quản lý nhân sự |
| `/my-admin/flash-sales/` | Flash Sale |
| `/my-admin/coupons/` | Mã giảm giá |
| `/my-admin/returns/` | Quản lý trả hàng |
| `/my-admin/news/` | Quản lý tin tức |
| `/admin/` | Django Admin gốc |

---

## 7. Xử Lý Lỗi Thường Gặp

### 7.1. Lỗi kết nối Database

```
django.db.utils.OperationalError: could not connect to server
```

**Nguyên nhân:** PostgreSQL chưa chạy hoặc sai thông tin kết nối.

**Cách xử lý:**
1. Kiểm tra PostgreSQL Service đang chạy: `Services` → tìm `postgresql-x64-18`
2. Kiểm tra lại `PASSWORD` trong `settings.py`
3. Đảm bảo database `bandienthoai_db2` đã được tạo

### 7.2. Lỗi GDAL Library Not Found

```
OSError: [WinError 126] The specified module could not be found
```

**Nguyên nhân:** Tên file GDAL DLL không khớp.

**Cách xử lý:**

1. Kiểm tra tên file thực tế:
```powershell
Get-ChildItem "C:\OSGeo4W\bin" -Filter "gdal3*.dll" | Select-Object Name
```

2. Sửa dòng 142 trong [settings.py](file:///d:/dowload/LTGIS-dev/LTGIS-dev/project-gis/webbanhang/settings.py#L142):
```python
# Thay 'gdal310.dll' bằng tên file đúng
GDAL_LIBRARY_PATH = os.path.join(OSGEO4W_ROOT, 'bin', 'gdal310.dll')
```

### 7.3. Lỗi PostGIS Extension

```
django.db.utils.ProgrammingError: extension "postgis" does not exist
```

**Cách xử lý:** Cài PostGIS cho PostgreSQL (xem [Mục 2.2](#22-cài-postgresql))

### 7.4. Lỗi `psycopg2` không cài được

```
Error: Failed building wheel for psycopg2
```

**Cách xử lý:** Dùng bản binary thay thế:
```powershell
pip install psycopg2-binary
```

### 7.5. Lỗi PowerShell Script Execution

```
File .\venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled
```

**Cách xử lý:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 7.6. Lỗi Import Module

```
ModuleNotFoundError: No module named 'openpyxl'
```

**Cách xử lý:** Đảm bảo đã kích hoạt venv và cài đủ packages:
```powershell
.\venv\Scripts\Activate.ps1
pip install openpyxl Pillow groq
```

### 7.7. Lỗi "Python was not found" khi tạo venv

```
Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
```

**Nguyên nhân:** Windows tự động thêm alias `python.exe` trỏ tới Microsoft Store, làm ghi đè lệnh python thật bạn đã cài đặt.

**Cách xử lý:**
1. Mở Start Menu, gõ và chọn **"Manage app execution aliases"** (hoặc vào Settings > Apps > Advanced app settings > App execution aliases).
2. Cuộn xuống tìm `python.exe` và `python3.exe` (thường có icon App Installer).
3. Chuyển nút gạt sang **Off** để tắt chúng.
4. Mở lại terminal mới và chạy lại lệnh.

**Nếu vẫn không được**, sử dụng đường dẫn tuyệt đối của Python để tạo venv (thay `Python314` bằng phiên bản của bạn):
```powershell
& "C:\Users\HP\AppData\Local\Programs\Python\Python314\python.exe" -m venv venv
```

---

## 📋 Tóm Tắt Nhanh (Quick Start)

```powershell
# 1. Tạo database
psql -U postgres -c "CREATE DATABASE bandienthoai_db2;"
psql -U postgres -d bandienthoai_db2 -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 2. Import dữ liệu
pg_restore -U postgres -d bandienthoai_db2 --no-owner --no-privileges "d:\dowload\LTGIS-dev\LTGIS-dev\phone_store.sql"

# 3. Setup Python
cd "d:\dowload\LTGIS-dev\LTGIS-dev\project-gis"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install django==6.0.1 psycopg2-binary Pillow openpyxl groq

# 4. Sửa password database trong settings.py (nếu khác 123456)

# 5. Chạy
python manage.py migrate
python manage.py runserver

# 6. Mở trình duyệt → http://127.0.0.1:8000/
```

---

> [!TIP]
> Nếu muốn tạo tài khoản admin mới, chạy:
> ```powershell
> python manage.py createsuperuser
> ```
> Sau đó truy cập `/admin/` để quản lý qua Django Admin gốc,
> hoặc đăng nhập tại `/login/` và truy cập `/my-admin/` để dùng admin panel custom.

## 8. Video Hướng Dẫn & Báo Cáo

👉 Xem video tại đây:  
https://drive.google.com/drive/u/0/folders/10SwC2eFRHNPuQuD7DaJJ0puZpOvL_jFe
