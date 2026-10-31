# Lái Việt — Hệ thống quản lý và đặt thuê xe du lịch trực tuyến

Ứng dụng tiếng Việt: **React + Vite**, **Node.js + Express**, **Microsoft SQL Server**. Phát triển tiếp từ `souce.zip` và SQL V2 bạn cung cấp; độc lập với dự án LTGIS có sẵn.

## Chạy với SQL Server của bạn

Yêu cầu: Node.js 22+, npm, SQL Server 2019/2022; bật TCP/IP và SQL Authentication nếu dùng tài khoản SQL. Đặt hostname và cổng TCP riêng, không đặt tên instance `localhost\SQLEXPRESS` vào `DB_SERVER`.

```bash
cd car-rental-system
npm run install:all
```

1. Sao chép `backend/.env.example` thành `backend/.env`.
2. Sửa `DB_SERVER`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE` theo SQL Server của bạn. Không commit `.env`.
3. Đặt `JWT_SECRET` ngẫu nhiên, tối thiểu 24 ký tự. Tạo bằng `node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"`.
4. Sao lưu database hiện có trước khi nâng cấp.

```bash
npm run db:migrate
npm run db:seed
npm run dev
```

Frontend: cổng **5173**. API: cổng **5000**. Vite proxy `/api` sang backend. React không kết nối trực tiếp tới SQL Server.

`db:migrate` chạy file gộp `database/CarRentalDB.sql`, hỗ trợ cài mới hoặc bổ sung database V2 đã có. Không xóa dữ liệu. `database/reference/DatThueXeDuLich.sql` giữ nguyên làm tài liệu đối chiếu; **không chạy file này thay cho migration của ứng dụng**: bản gốc thiếu schema nền và có câu `EXEC ... @Resource=CONCAT(...)` cần sửa trong một tác vụ SQL riêng. Migration mới không phụ thuộc các procedure trong file gốc.

`db:seed` thêm tài khoản và xe demo khi chưa có, không đặt lại mật khẩu tài khoản cũ. Nếu dữ liệu cũ vi phạm ràng buộc, hãy kiểm tra lỗi và dữ liệu; không xóa bản ghi để vượt qua lỗi.

### SQL Server bằng Docker (tùy chọn)

Nếu đã có SQL Server thì bỏ qua. Tạo `.env` ở thư mục gốc chứa `MSSQL_SA_PASSWORD` đủ mạnh:

```bash
docker compose up -d --wait
```

Đặt cùng mật khẩu vào `backend/.env`, `DB_SERVER=localhost`, `DB_PORT=1433`, `DB_USER=sa`. `DB_TRUST_SERVER_CERTIFICATE=true` chỉ dành cho SQL tự ký ở môi trường phát triển. Môi trường thật dùng certificate hợp lệ, `DB_ENCRYPT=true`, `DB_TRUST_SERVER_CERTIFICATE=false`. Volume giữ dữ liệu; không dùng `docker compose down -v` khi còn cần dữ liệu.

## Chạy demo khi chưa có SQL Server

```bash
npm run dev:demo
```

Chế độ demo được chọn rõ ràng, dùng dữ liệu trong RAM, mất dữ liệu khi khởi động lại. `npm start` và `npm run dev` vẫn bắt buộc SQL Server, dừng nếu kết nối thất bại; không âm thầm dùng bộ nhớ.

| Vai trò    | Tài khoản  | Mật khẩu       |
| ---------- | ---------- | -------------- |
| Admin      | `admin`    | `Admin@123`    |
| Nhân viên  | `employee` | `Employee@123` |
| Khách hàng | `customer` | `Customer@123` |

Tài khoản chỉ dành cho demo/đồ án. Thay hoặc bỏ seed demo trước khi triển khai công khai. Đăng ký luôn tạo khách hàng, không nhận quyền admin từ request.

## Tính năng theo ảnh yêu cầu

| Nhóm                 | Triển khai                                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------- |
| Quy trình thuê       | Chọn xe, khoảng giờ, báo giá, kiểm tra trống, đặt, xác nhận/từ chối, nhận, trả, thanh toán, hoàn tất/hủy  |
| Chống trùng          | So sánh khoảng `[nhận, trả)`, cho phép tiếp giáp; giao dịch SQL bảo vệ cả các yêu cầu đặt đồng thời       |
| Trạng thái           | Đơn chờ/xác nhận/đang thuê/hoàn tất/hủy/từ chối; xe trống/đã đặt/đang thuê/bảo trì/tạm ngưng              |
| Nhận–trả             | Thời gian, số km, nhiên liệu, tình trạng, ghi chú; phí hư hại/nhiên liệu/vệ sinh/khác; đưa xe vào bảo trì |
| Giá và hợp đồng      | Giá ngày chốt lúc đặt, cọc theo xe, phí trễ/hủy; hợp đồng tạo khi xác nhận, xem/in                        |
| Thanh toán/thông báo | Mô phỏng thành công/thất bại, chống lặp, giới hạn thu/hoàn; thông báo trong app, nhắc sắp nhận xe         |
| Phân quyền/nhật ký   | Khách chỉ xem đơn của mình; nhân viên xử lý nghiệp vụ; admin quản trị tài khoản và xem ai sửa gì          |
| Kiểm thử             | HTTP business tests, đồng thời, SQL integration tùy chọn, smoke test trình duyệt; xem `TEST_CASES.md`     |

### Trạng thái và tính tiền

```text
pending → confirmed → renting → ghi nhận trả xe → completed
pending → rejected
pending / confirmed → cancelled
```

Trả xe ghi `ActualReturnDate` và phiếu trả; đơn còn `renting` cho tới khi thanh toán đủ và nhân viên hoàn tất. Đơn đã trả không chặn lịch xe. Không hủy khi đang giữ xe. Không nhận xe trước giờ thuê hoặc thiếu cọc; không hoàn tất khi chưa trả/chưa đủ tiền.

- Số ngày = `ceil((trả - nhận) / 24 giờ)`, tối thiểu 1. Ngày trả sau ngày nhận; ngày nhận của đơn mới phải trong tương lai, tối đa thuê 366 ngày.
- Tiền thuê = số ngày × giá ngày đã chốt. Cọc là một phần tiền thuê, không cộng thêm vào tổng; tỷ lệ mặc định 30%, cấu hình theo xe.
- Phí trả trễ = số ngày trễ làm tròn lên × giá ngày đã chốt × 150%, làm tròn VND. Không giảm tiền thuê hoặc phạt trả sớm.
- Hủy đơn chờ miễn phí; hủy đã xác nhận thu 50% cọc. Tổng phải trả sau hủy là phí hủy. Tiền đã thu thừa được nhân viên/admin hoàn mô phỏng.
- Ví dụ 1.000.000đ/ngày, thuê 2 ngày: tiền thuê 2.000.000đ, cọc 600.000đ. Trả trễ 2 giờ: phí trễ 1.500.000đ, tổng 3.500.000đ, còn 2.900.000đ nếu đã cọc. Hủy sau xác nhận: phí 300.000đ, hoàn 300.000đ nếu đã cọc đủ.
- Xe bảo trì/tạm ngưng không nhận đơn mới. Xe đã có lịch vẫn cho đặt khoảng khác không chồng. Xe đang thuê quá giờ chưa trả chặn lịch mới tới khi được xử lý.
- Thu tối đa khoản còn nợ; hoàn tối đa phần thu thừa. `idempotencyKey` chống ghi nhận hai lần cùng yêu cầu. Thanh toán thất bại có lịch sử nhưng không cộng tiền.

**Thanh toán chỉ mô phỏng**, không thu tiền thật, không tích hợp ngân hàng/VNPay/MoMo. Thông báo lưu trong ứng dụng, không gửi SMS/email. Nhân viên bấm gửi nhắc cho đơn xác nhận sắp nhận trong 24 giờ; chống lặp theo đơn. Có thể tích hợp scheduler có xác thực sau này.

### Bảng quyền

| Thao tác                            | Khách hàng   | Nhân viên         | Admin   |
| ----------------------------------- | ------------ | ----------------- | ------- |
| Xem xe/lịch                         | Có           | Có                | Có      |
| Đặt, xem, thanh toán/hủy            | Đơn của mình | Nghiệp vụ mọi đơn | Mọi đơn |
| Xác nhận/từ chối, nhận/trả/hoàn tất | Không        | Có                | Có      |
| Hoàn tiền, gửi nhắc, báo cáo        | Không        | Có                | Có      |
| Quản lý xe                          | Không        | Có                | Có      |
| Quản lý tài khoản/vai trò, nhật ký  | Không        | Không             | Có      |

## Kiểm thử và build

```bash
npm test
npm run build
```

Business tests dùng store bộ nhớ chỉ trong test và gọi HTTP Express thật. SQL integration phải có SQL Server với quyền tạo database test, không trỏ vào DB đang dùng. Xem `TEST_CASES.md` để biết kết quả thực chạy và giới hạn.

Sau build, backend phục vụ cả `frontend/dist` và API trên cổng 5000:

```bash
npm start
```

Triển khai công khai cần HTTPS, `FRONTEND_ORIGIN` đúng domain, bí mật riêng và tài khoản database hạn chế quyền. JWT lưu ở trình duyệt để phục vụ đồ án; khi triển khai thật nên dùng cookie HttpOnly và rà soát bảo mật.

## Cấu trúc và API

```text
backend/         Express, domain rules, SQL store, migration/seed, tests
frontend/        React, màn khách hàng/nhân viên/admin, assets cục bộ
database/        CarRentalDB.sql (file gộp), reference/ chứa SQL gốc
scripts/         dev runner và kiểm thử trình duyệt
compose.yaml     SQL Server development tùy chọn
TEST_CASES.md    đối chiếu kiểm thử
```

API prefix `/api`, JWT `Authorization: Bearer <token>`. JSON `{success:true,data}` hoặc `{success:false,message}`. Entity PascalCase; auth user camelCase.

| Endpoint (sau `/api`)                                                                                           | Mục đích                          |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `POST /auth/register`, `/auth/login`; `GET /auth/me`; `PUT /auth/profile`                                       | Tài khoản                         |
| `GET /cars`, `/cars/:id`, `/cars/:id/availability`, `/cars/:id/schedule`                                        | Xe/lịch, không lộ thông tin khách |
| `POST /cars`; `PUT /cars/:id`, `/cars/:id/status`                                                               | Quản lý xe                        |
| `POST /orders/quote`, `/orders`; `GET /orders`, `/orders/:id`                                                   | Báo giá/đặt thuê                  |
| `PUT /orders/:id/confirm`, `/reject`, `/pickup`, `/return`, `/complete`, `/cancel`                              | Quy trình đơn                     |
| `GET /orders/:id/contract`                                                                                      | Hợp đồng HTML có kiểm tra quyền   |
| `POST /payments`; `GET /payments/order/:orderId`                                                                | Thanh toán                        |
| `GET /notifications`; `PUT /notifications/read-all`, `/notifications/:id/read`; `POST /notifications/reminders` | Thông báo                         |
| `GET /reports`, `/audit-logs`, `/users`; `POST /users`; `PUT /users/:id`                                        | Báo cáo/quản trị                  |
| `GET /health`                                                                                                   | Kiểm tra kết nối                  |

Thay đổi đơn, xe, tiền, thông báo và audit commit cùng transaction `SERIALIZABLE`, với `sp_getapplock` transaction-scoped. Khóa ghi dùng chung chống tranh chấp qua nhiều tiến trình Node, phù hợp đồ án. Quy mô lớn cần truy vấn SQL có phân trang và khóa theo xe/đơn thay cho tải toàn bộ bảng và tuần tự hóa mọi thao tác ghi.

## Lỗi thường gặp

- **SQL timeout:** kiểm tra SQL chạy, TCP/IP, đúng hostname/cổng, firewall. `localhost` ở cloud không phải SQL Server trên laptop của bạn.
- **Login failed:** kiểm tra SQL Authentication và quyền tài khoản. Không gửi mật khẩu qua chat.
- **Database chưa có:** migrate bằng tài khoản có quyền tạo DB, hoặc tạo `CarRentalDB` trước trong SSMS.
- **Certificate:** dùng CA tin cậy; chỉ trust certificate tự ký trong môi trường phát triển.
- **Frontend lỗi API:** backend phải chạy ở 5000 hoặc sửa Vite proxy/VITE_API_URL. Production dùng backend sau build; Vite preview không có proxy dev.
- **Tài khoản demo cũ:** seed không thay mật khẩu tài khoản đã tồn tại; dùng mật khẩu hiện có.

## Kiểm thử trình duyệt và ảnh giao diện

```bash
npm ci
npx playwright install chromium
npm run test:browser
```

Trên cloud đã có `/usr/bin/chromium`, không cần tải trình duyệt lần nữa. Máy khác dùng Chromium do Playwright cài; hoặc đặt `CHROMIUM_PATH` tới trình duyệt của bạn. Test tự chạy backend riêng ở 5101 và Vite ở 5176, dùng bộ nhớ tách biệt, không sửa SQL Server. Cần để hai cổng này trống.

Ảnh thực chụp từ bản ứng dụng:

- `docs/screenshots/catalog-desktop.png`: trang chọn xe desktop.
- `docs/screenshots/catalog-mobile.png`: giao diện điện thoại.
- `docs/screenshots/completed-order.png`: đơn hoàn tất sau nhận–trả trễ, phụ phí, thanh toán.
- `docs/screenshots/admin-dashboard.png`: báo cáo quản trị.

Xe trong dữ liệu demo dùng SVG minh họa cục bộ. Admin có thể cập nhật URL ảnh thực cho từng xe.


## Chạy file SQL gộp trực tiếp trong SSMS

Chỉ chạy `database/CarRentalDB.sql`. File đã chứa toàn bộ schema và bổ sung runtime theo đúng thứ tự; không cần dán thêm hai file cũ.

1. Tạo database nếu chưa có; chọn database đúng tên trong SSMS.
2. Mở `database/CarRentalDB.sql`, kiểm tra dropdown database trước khi bấm F5.
3. Chạy `npm run db:seed` trong terminal để thêm tài khoản/xe mẫu, sau đó `npm run dev`.

Hoặc giữ cách tự động: cấu hình `backend/.env`, chạy `npm run db:migrate`. Migration chạy toàn bộ file gộp trong một transaction. SQL gốc trong `database/reference/` chỉ để đối chiếu.


## Sửa lỗi 51040 nhầm PaymentStatus với Status

Bản cập nhật ngày 01/11/2026 chọn ràng buộc bằng mã cột và quan hệ phụ thuộc trong metadata SQL Server, thay cho tìm chuỗi `Status` trong định nghĩa. Nhờ đó CHECK của `PaymentStatus` không bị xem là CHECK của `Status`; các ràng buộc kiểm tra thanh toán được giữ nguyên.

Nếu bản trước báo lỗi với tên dạng `CK__RentalOrd__Payme__...`, tải lại `database/CarRentalDB.sql` bản sửa, mở cửa sổ truy vấn mới trong SSMS, chọn đúng database hiện có và chạy lại toàn bộ file. Không cần xóa database hoặc bỏ CHECK. Các bảng/cột đã có được giữ lại. Nếu một CHECK thực sự phụ thuộc nhiều cột, script vẫn dừng để yêu cầu kiểm tra riêng thay vì làm mất các điều kiện của dữ liệu.
