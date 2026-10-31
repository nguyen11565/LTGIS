# Kiểm thử nghiệp vụ thuê xe

Bộ kiểm thử HTTP dùng `node:test`, Supertest và **bộ lưu trữ trong bộ nhớ chỉ dành cho kiểm thử**. Mỗi ca có dữ liệu riêng, thời gian giả lập cố định và gọi API thật của Express. Máy chủ chạy ứng dụng sử dụng SQL Server; các kiểm thử dưới đây không thay thế việc kiểm tra kết nối, migration hoặc tranh chấp giữa nhiều tiến trình trên SQL Server.

Chạy từ thư mục `backend`:

```bash
npm ci
npm test
```

## Kết quả lần chạy gần nhất

Ngày chạy: **31/10/2026**. Lệnh `npm test` kết thúc mã **0**: **32 ca tổng cộng, 31 đạt, 0 lỗi, 1 bỏ qua**. Ca bỏ qua là tích hợp SQL Server thực (SQL-01), chưa được chạy vì máy hiện tại chưa có SQL Server khả dụng.

Lần chạy đầu trong sandbox bị chặn mở socket localhost (`listen EPERM 127.0.0.1`). Sau khi chạy lại trong môi trường cho phép socket cục bộ, toàn bộ 31 ca HTTP nghiệp vụ đã chạy và đạt. Kết quả bên dưới là kết quả thực của lần chạy này; ca SQL bị bỏ qua không được tính là đạt.

## Bảng expected/actual

Các ca UC tham chiếu tài liệu Word đặc tả UC01–UC22 người dùng bổ sung. Quyền quản lý xe theo UC18 thuộc quản trị viên; nhân viên tiếp tục thực hiện nghiệp vụ bàn giao và nhận trả qua đơn thuê.

| Mã                 | Tình huống                                                           | Kết quả mong đợi                                                                            | Actual |
| ------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------ |
| AUTH-01            | Đăng ký gửi kèm role admin; đăng ký lặp                              | Luôn tạo customer; cấm trang quản trị; chặn trùng                                           | Đạt    |
| AUTH-02            | Chưa đăng nhập, sai mật khẩu, mật khẩu yếu, truy cập đơn người khác  | Trả 401/400/403; không đọc/hủy/thanh toán được đơn người khác                               | Đạt    |
| AUTH-03            | Khóa người dùng đã có token                                          | Token cũ không dùng tiếp được                                                               | Đạt    |
| DATE-01            | Ngày sai định dạng, thiếu múi giờ, ngược hoặc trong quá khứ          | Trả 400; không lưu đơn lỗi                                                                  | Đạt    |
| PRICE-01           | Thuê 24 giờ 1 phút; đổi giá xe sau đặt                               | Tính hai ngày; cọc 30%; giữ đơn giá đã chốt                                                 | Đạt    |
| SCHEDULE-01        | Trùng toàn phần, nằm trong, bao phủ, giao hai đầu; nối sát giờ       | Tất cả khoảng giao nhau bị 409; khoảng nối sát được đặt                                     | Đạt    |
| SCHEDULE-02        | Hai khách gửi đặt cùng xe, cùng lúc                                  | Chính xác một 201 và một 409; chỉ có một đơn                                                | Đạt    |
| SCHEDULE-03        | Xe bảo trì; hủy đơn rồi đặt lại                                      | Xe bảo trì bị chặn; lịch được giải phóng sau hủy                                            | Đạt    |
| RBAC-01            | Khách gọi thao tác nhân viên/quản trị                                | Tất cả bị 403                                                                               | Đạt    |
| STATE-01           | Nhận khi chưa xác nhận/chưa cọc; xác nhận hai lần; hoàn tất sớm      | Chặn sai luồng; không chuyển trạng thái                                                     | Đạt    |
| CONTRACT-01        | Xác nhận và tải hợp đồng; khách khác tải                             | Tạo HTML hợp đồng đúng mã; khách khác bị chặn                                               | Đạt    |
| PAY-01             | Mô phỏng thanh toán thất bại rồi thử lại                             | Lưu giao dịch failed, không ghi có; lần mới có thể thành công                               | Đạt    |
| PAY-02             | Gửi lại cùng idempotency key; sửa số tiền trên key cũ                | Chỉ một khoản ghi có; chặn payload bị sửa                                                   | Đạt    |
| PAY-03             | Số tiền âm/vượt dư nợ; khách tự hoàn tiền                            | Chặn số tiền sai; chỉ nhân viên/admin được hoàn                                             | Đạt    |
| CANCEL-01          | Hủy sau xác nhận và thanh toán cọc                                   | Phí 50% cọc; chỉ hoàn phần dư; cấm xác nhận lại                                             | Đạt    |
| RETURN-01          | Bàn giao, hủy khi đang thuê, hoàn tất khi còn nợ                     | Lưu biên bản nhận; chặn hủy; chặn hoàn tất còn nợ                                           | Đạt    |
| RETURN-02          | Trả ở tương lai, km giảm, phí âm, trả trễ và phí hư hỏng/nhiên liệu  | Chặn dữ liệu sai; tính 150%/ngày trễ; cộng đúng phí; chuyển bảo trì                         | Đạt    |
| E2E-01             | Đặt → xác nhận → cọc → nhận → trả → thanh toán → hoàn tất            | Đơn completed/paid, xe available, đủ thông báo và audit                                     | Đạt    |
| NOTIFY-01          | Gửi nhắc nhận hai lần; đánh dấu thông báo khách khác                 | Không gửi nhắc trùng; chỉ chủ thông báo được đánh dấu đọc                                   | Đạt    |
| PAY-04             | Gửi thanh toán lặp đồng thời và hai lần quyết toán đồng thời         | Không thu hai lần; không vượt dư nợ                                                         | Đạt    |
| CANCEL-02          | Đã cọc nhưng hủy trước xác nhận                                      | Phí 0, hoàn toàn bộ cọc, cấm cọc tiếp đơn hủy                                               | Đạt    |
| CAR-01             | Tạm ngưng xe còn đơn; từ chối đơn và đặt lại                         | Chặn tạm ngưng; lịch giải phóng sau từ chối                                                 | Đạt    |
| PRICE-02           | Giá ngày VND lẻ và trả trễ                                           | Phí làm tròn nguyên VND, số dư thanh toán được, hoàn tất được                               | Đạt    |
| AUTH-04 / UC02     | Đăng nhập bằng tên hoặc email viết hoa                               | Cùng tài khoản/đúng vai trò; sai mật khẩu bị 401                                            | Đạt    |
| USER-01 / UC19     | Tạo nhân viên, trùng email/điện thoại, đọc log tạo tài khoản         | Chỉ admin được tạo; dữ liệu trùng bị 409; mật khẩu mã hóa và không lộ trong response/audit  | Đạt    |
| USER-02 / UC19–20  | Đổi vai trò người đã đăng nhập; admin tự khóa/hạ quyền               | Quyền mới áp dụng ngay token cũ; chặn admin tự khóa/hạ quyền                                | Đạt    |
| CAR-02 / UC18      | Nhân viên gọi thêm/sửa/tạm ngưng xe; admin lưu xe                    | Nhân viên bị 403; admin lưu hợp lệ; chặn biển số trùng và đặt xe tạm ngưng                  | Đạt    |
| CONTRACT-02 / UC17 | Sửa điều khoản chứa HTML trước bàn giao; sửa sau bàn giao            | Chỉ nhân viên/admin được sửa trước nhận; HTML được escape; giữ giá đã chốt; sau nhận bị 409 | Đạt    |
| REPORT-01 / UC22   | Lọc từng cửa sổ ngày có cọc, thất bại và hoàn tiền                   | Đếm đơn theo ngày tạo, thu thành công trừ hoàn tiền; loại thất bại; tổng theo xe/tháng khớp | Đạt    |
| REPORT-02 / UC22   | Bộ lọc thiếu ngày, đảo ngày, sai múi giờ, quá dài hoặc không dữ liệu | Trả 400 với bộ lọc sai; khoảng rỗng trả 0; khách không được đọc báo cáo                     | Đạt    |
| REPORT-03 / UC22   | Thuê thực tế hai ngày, báo cáo chỉ chọn một ngày ở giữa              | Chỉ tính một ngày khai thác, tỷ lệ 100% cho đúng xe; không đếm đơn/doanh thu ngoài ngày tạo | Đạt    |

## Tích hợp SQL Server thực — chưa chạy

`backend/test/sql.integration.test.js` chỉ chạy khi bật rõ ràng:

```bash
# backend/.env hoặc biến môi trường phải có DB_SERVER, DB_USER, DB_PASSWORD,
# DB_PORT, DB_ENCRYPT, DB_TRUST_SERVER_CERTIFICATE phù hợp.
# Lệnh thực thi tích hợp có cờ bật (test tự đọc backend/.env):
RUN_SQL_TESTS=1 npm test
```

Trên PowerShell: `$env:RUN_SQL_TESTS='1'; npm test`.

| Mã     | Kịch bản                                                                                                                                                                                   | Expected                                                                                                                                 | Actual                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| SQL-01 | Tạo CSDL kiểm thử riêng, chạy migration hai lần, seed hai lần, đặt cùng lịch từ hai pool độc lập, gửi lặp giao dịch thanh toán, bàn giao/trả trễ/quyết toán/hoàn tất và đọc dữ liệu đã lưu | Không nhân đôi dữ liệu; đúng một đơn; đúng một giao dịch lặp; tiền phí và trạng thái lưu chính xác; có hợp đồng/biên bản/audit/thông báo | **Bỏ qua — chưa có SQL Server khả dụng trong máy hiện tại** |

Tài khoản SQL dùng kiểm thử cần quyền `CREATE DATABASE` và `DROP DATABASE`. Test tự sinh tên dạng `CarRentalTest_<24 ký tự hex>`, chỉ migrate/seed trên CSDL vừa tạo, đóng các pool rồi xóa đúng CSDL đó trong `finally`. Không dùng, ghi đè, truncate hoặc xóa CSDL nghiệp vụ đang có. Migration hiện chạy file gộp `CarRentalDB.sql` (giữ nguyên nội dung và thứ tự batch của `schema.sql` rồi `002_runtime.sql`) được duy trì cùng ứng dụng; không tuyên bố đã thực thi file SQL gốc người dùng gửi.

Bảng trên chỉ báo cáo kiểm thử backend. Kết quả build/giao diện trình duyệt được ghi riêng trong hướng dẫn bàn giao của dự án.

## Kiểm tra frontend thực tế bằng Chromium

Lệnh tại thư mục gốc: `npm run test:browser` (sau `npm ci` ở gốc và cài Chromium nếu máy chưa có). Kết quả ngày 31/10/2026: **PASS**, không phát sinh lỗi JavaScript trên trang. Đây là test trình duyệt gọi API Express thật với memory adapter được chọn rõ ràng, không phải bằng chứng SQL Server đã chạy.

| Luồng giao diện                                            | Actual |
| ---------------------------------------------------------- | ------ |
| Catalog desktop 1440px, mobile 390px, không tràn ngang     | Đạt    |
| Khách hàng đăng nhập, kiểm tra giá/lịch, đặt xe            | Đạt    |
| Thanh toán thất bại không cộng tiền; đặt cọc thành công    | Đạt    |
| Nhân viên xác nhận, mở hợp đồng trong cửa sổ mới           | Đạt    |
| Biên bản nhận xe, trả trễ, phí phát sinh, trả đủ, hoàn tất | Đạt    |
| Admin xem dashboard, tạo nhân viên, xem dữ liệu audit      | Đạt    |
| Khách hàng xem thông báo xác nhận                          | Đạt    |

`npm run build`: **PASS**, 1596 modules, production assets tạo trong `frontend/dist`. Đã kiểm tra Express trả SPA tại `/`, `/orders`, `/manage`, trả 404 cho API không tồn tại và health phân biệt memory với SQL Server.

SQL Server thật chưa được kiểm thử trong máy cloud: image registry của Microsoft chuyển hướng sang domain tải không nằm trong allowlist, trả HTTP 403; tải gói server chính thức cũng bị chặn. Không bỏ TLS hoặc checksum để vượt lỗi. Cần chạy SQL-01 với SQL Server của bạn để xác nhận migration, dữ liệu cũ và khóa đồng thời ở tầng SQL. Tệp SQL bạn cung cấp được giữ nguyên byte-for-byte (đã đối chiếu SHA256).


## Thay doi file SQL gop (01/11/2026)

Da gop `schema.sql` va `002_runtime.sql` vao `database/CarRentalDB.sql`, giu nguyen thu tu va dau GO. Da doi duong dan trong migration, kiem tra noi dung cac batch tuong duong hai file cu va kiem tra cu phap JavaScript cua migration. Khong tuyen bo da chay file gop tren SQL Server that; ca SQL-01 van can SQL Server kha dung de xac nhan.


## Hồi quy ràng buộc Status / PaymentStatus (01/11/2026)

Lỗi người dùng báo `51040` xuất phát từ bộ lọc tên cột theo chuỗi con: `Status` đã khớp nhầm `PaymentStatus`. Migration được sửa để đối chiếu mã cột thật qua metadata SQL Server. Không xóa hoặc vô hiệu hóa ràng buộc thanh toán để vượt lỗi.

Ca **SQL-02** trong `backend/test/sql.constraint-regression.test.js` chỉ chạy với `RUN_SQL_TESTS=1` và SQL Server thật. Nó tạo database ngẫu nhiên riêng, kiểm tra migration trên database mới, thêm các CHECK tách biệt ở mức cột/bảng, xác nhận Status được mở rộng còn PaymentStatus giữ nguyên định nghĩa và trạng thái tin cậy; mã thanh toán sai vẫn bị từ chối. Một CHECK thật sự liên quan cả hai cột vẫn phải bị chặn bằng lỗi 51040; các cập nhật trước đó trong migration phải rollback, không sửa dữ liệu đã có. Test chỉ xóa database do chính nó tạo.

**Trạng thái SQL-02: chưa thực thi trên SQL Server thật** vì môi trường cloud chưa có SQL Server khả dụng. Các số liệu test đạt trước đó là kết quả lịch sử, không tính ca mới này là đã đạt.
