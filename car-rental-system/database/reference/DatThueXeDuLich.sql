/*
   GHI CHÚ:
   - Các từ khóa SQL Server như SELECT, INSERT, UPDATE, CREATE TABLE... bắt buộc giữ nguyên.
   - Tên bảng/cột tiếng Anh được giữ nguyên để backend Node.js hiện tại không bị lỗi.
   - Phần chú thích, cảnh báo và mô tả nghiệp vụ đã được Việt hóa.
*/

/* =====================================================================
   CƠ SỞ DỮ LIỆU HỆ THỐNG THUÊ XE - BẢN NÂNG CẤP V2
   Mục tiêu: bổ sung CSDL để khớp UC01-UC22 + Sơ đồ lớp hiện tại
   Công nghệ: ReactJS + Node.js/Express + SQL Server

   CÁCH DÙNG:
   1) Chạy schema.sql hiện tại trước (nếu DB chưa có).
   2) Chạy file này sau.
   3) File này cố gắng idempotent: có thể chạy lại an toàn ở mức schema.

   LƯU Ý TƯƠNG THÍCH:
   - Giữ nguyên các bảng/cột cũ để backend hiện tại không bị vỡ.
   - Bổ sung bảng/cột mới theo nghiệp vụ, chưa bắt buộc backend cũ dùng ngay.
   ===================================================================== */

USE CarRentalDB;
GO

SET XACT_ABORT ON;
GO

/* =====================================================================
   1. NGƯỜI DÙNG: UC01, UC03, UC19, UC20
   - Số điện thoại phải duy nhất nếu có (UC01: email/số điện thoại chưa tồn tại)
   - Bổ sung địa chỉ cho UC03
   - Bổ sung mô hình phân quyền theo vai trò: Roles, Permissions, RolePermissions
   ===================================================================== */

IF COL_LENGTH('dbo.Users', 'Address') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD Address NVARCHAR(255) NULL;
END
GO

-- Tạo chỉ mục duy nhất cho số điện thoại nếu dữ liệu hiện tại không bị trùng.
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.Users') AND name = 'UX_Users_Phone'
)
BEGIN
    IF NOT EXISTS (
        SELECT Phone
        FROM dbo.Users
        WHERE Phone IS NOT NULL
        GROUP BY Phone
        HAVING COUNT(*) > 1
    )
    BEGIN
        CREATE UNIQUE INDEX UX_Users_Phone
            ON dbo.Users(Phone)
            WHERE Phone IS NOT NULL;
    END
    ELSE
    BEGIN
        PRINT N'[CẢNH BÁO] Không tạo UX_Users_Phone vì dữ liệu hiện tại có số điện thoại trùng.';
    END
END
GO

IF OBJECT_ID('dbo.Roles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Roles (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Code NVARCHAR(30) NOT NULL UNIQUE,
        Name NVARCHAR(100) NOT NULL,
        Description NVARCHAR(500) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_Roles_IsActive DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_Roles_CreatedAt DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_Roles_UpdatedAt DEFAULT GETDATE()
    );
END
GO

IF OBJECT_ID('dbo.Permissions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Permissions (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Code NVARCHAR(100) NOT NULL UNIQUE,
        Name NVARCHAR(150) NOT NULL,
        Description NVARCHAR(500) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_Permissions_IsActive DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_Permissions_CreatedAt DEFAULT GETDATE()
    );
END
GO

IF OBJECT_ID('dbo.RolePermissions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RolePermissions (
        RoleId INT NOT NULL,
        PermissionId INT NOT NULL,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_RolePermissions_CreatedAt DEFAULT GETDATE(),
        CONSTRAINT PK_RolePermissions PRIMARY KEY (RoleId, PermissionId),
        CONSTRAINT FK_RolePermissions_Role FOREIGN KEY (RoleId) REFERENCES dbo.Roles(Id),
        CONSTRAINT FK_RolePermissions_Permission FOREIGN KEY (PermissionId) REFERENCES dbo.Permissions(Id)
    );
END
GO

-- Khởi tạo 3 vai trò mặc định đúng với backend hiện tại.
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE Code = 'customer')
    INSERT INTO dbo.Roles(Code, Name, Description) VALUES ('customer', N'Khách hàng', N'Người dùng đặt thuê xe');
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE Code = 'employee')
    INSERT INTO dbo.Roles(Code, Name, Description) VALUES ('employee', N'Nhân viên', N'Nhân viên xử lý đơn, giao trả xe, thanh toán, hợp đồng');
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE Code = 'admin')
    INSERT INTO dbo.Roles(Code, Name, Description) VALUES ('admin', N'Quản trị viên', N'Quản trị hệ thống');
GO

-- Các quyền cốt lõi theo UC11-UC22.
DECLARE @PermissionSeed TABLE(Code NVARCHAR(100), Name NVARCHAR(150));
INSERT INTO @PermissionSeed(Code, Name) VALUES
('ORDER_PROCESS', N'Xử lý đơn thuê'),
('ORDER_CONFIRM', N'Xác nhận đơn'),
('VEHICLE_HANDOVER', N'Giao xe'),
('VEHICLE_RETURN', N'Nhận trả xe'),
('EXTRA_FEE_CALCULATE', N'Tính phí phát sinh'),
('PAYMENT_PROCESS', N'Xử lý thanh toán'),
('CONTRACT_MANAGE', N'Quản lý hợp đồng'),
('CAR_MANAGE', N'Quản lý xe'),
('USER_MANAGE', N'Quản lý người dùng'),
('PERMISSION_MANAGE', N'Phân quyền'),
('AUDIT_VIEW', N'Xem lịch sử thay đổi'),
('REPORT_VIEW', N'Thống kê - báo cáo');

INSERT INTO dbo.Permissions(Code, Name)
SELECT s.Code, s.Name
FROM @PermissionSeed s
WHERE NOT EXISTS (SELECT 1 FROM dbo.Permissions p WHERE p.Code = s.Code);
GO

-- Gán quyền mặc định: quản trị viên có toàn bộ quyền, nhân viên có các quyền nghiệp vụ.
DECLARE @AdminRoleId INT = (SELECT Id FROM dbo.Roles WHERE Code='admin');
DECLARE @EmployeeRoleId INT = (SELECT Id FROM dbo.Roles WHERE Code='employee');

INSERT INTO dbo.RolePermissions(RoleId, PermissionId)
SELECT @AdminRoleId, p.Id
FROM dbo.Permissions p
WHERE @AdminRoleId IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.RolePermissions rp
      WHERE rp.RoleId=@AdminRoleId AND rp.PermissionId=p.Id
  );

INSERT INTO dbo.RolePermissions(RoleId, PermissionId)
SELECT @EmployeeRoleId, p.Id
FROM dbo.Permissions p
WHERE @EmployeeRoleId IS NOT NULL
  AND p.Code IN (
      'ORDER_PROCESS','ORDER_CONFIRM','VEHICLE_HANDOVER','VEHICLE_RETURN',
      'EXTRA_FEE_CALCULATE','PAYMENT_PROCESS','CONTRACT_MANAGE'
  )
  AND NOT EXISTS (
      SELECT 1 FROM dbo.RolePermissions rp
      WHERE rp.RoleId=@EmployeeRoleId AND rp.PermissionId=p.Id
  );
GO

-- Giữ Users.Role để backend hiện tại vẫn chạy; bổ sung RoleId để đúng mô hình phân quyền theo vai trò.
IF COL_LENGTH('dbo.Users', 'RoleId') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD RoleId INT NULL;
END
GO

UPDATE u
SET RoleId = r.Id
FROM dbo.Users u
JOIN dbo.Roles r ON r.Code = u.Role
WHERE u.RoleId IS NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE name='FK_Users_RoleId'
)
BEGIN
    ALTER TABLE dbo.Users WITH CHECK
    ADD CONSTRAINT FK_Users_RoleId FOREIGN KEY(RoleId) REFERENCES dbo.Roles(Id);
END
GO

/* =====================================================================
   2. XE: UC04, UC18 + Sơ đồ lớp LoaiXe/HinhAnhXe
   ===================================================================== */

IF OBJECT_ID('dbo.CarTypes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CarTypes (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Name NVARCHAR(100) NOT NULL UNIQUE,
        Seats INT NULL,
        Description NVARCHAR(500) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_CarTypes_IsActive DEFAULT 1,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_CarTypes_CreatedAt DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_CarTypes_UpdatedAt DEFAULT GETDATE()
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.CarTypes WHERE Name=N'Khác')
    INSERT INTO dbo.CarTypes(Name, Description) VALUES (N'Khác', N'Loại xe mặc định sau khi nâng cấp dữ liệu');
GO

IF COL_LENGTH('dbo.Cars', 'CarTypeId') IS NULL
    ALTER TABLE dbo.Cars ADD CarTypeId INT NULL;
GO

UPDATE dbo.Cars
SET CarTypeId = (SELECT TOP 1 Id FROM dbo.CarTypes WHERE Name=N'Khác')
WHERE CarTypeId IS NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_Cars_CarType')
BEGIN
    ALTER TABLE dbo.Cars WITH CHECK
    ADD CONSTRAINT FK_Cars_CarType FOREIGN KEY(CarTypeId) REFERENCES dbo.CarTypes(Id);
END
GO

-- Tiền cọc theo xe: backend hiện đang tính 30%, vì vậy lưu tỷ lệ mặc định 30%.
IF COL_LENGTH('dbo.Cars', 'DepositRate') IS NULL
BEGIN
    ALTER TABLE dbo.Cars ADD DepositRate DECIMAL(5,2) NOT NULL
        CONSTRAINT DF_Cars_DepositRate DEFAULT 30.00;
END
GO

IF OBJECT_ID('dbo.CarImages', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CarImages (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        CarId INT NOT NULL,
        ImageUrl NVARCHAR(500) NOT NULL,
        Description NVARCHAR(500) NULL,
        SortOrder INT NOT NULL CONSTRAINT DF_CarImages_SortOrder DEFAULT 0,
        IsPrimary BIT NOT NULL CONSTRAINT DF_CarImages_IsPrimary DEFAULT 0,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_CarImages_CreatedAt DEFAULT GETDATE(),
        CONSTRAINT FK_CarImages_Car FOREIGN KEY(CarId) REFERENCES dbo.Cars(Id)
    );
END
GO

-- Chuyển dữ liệu ảnh cũ sang CarImages, đồng thời vẫn giữ Cars.ImageUrl để backend hiện tại không bị lỗi.
INSERT INTO dbo.CarImages(CarId, ImageUrl, IsPrimary)
SELECT c.Id, c.ImageUrl, 1
FROM dbo.Cars c
WHERE c.ImageUrl IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.CarImages i WHERE i.CarId=c.Id AND i.ImageUrl=c.ImageUrl
  );
GO

/* =====================================================================
   3. ĐƠN THUÊ XE: UC05-UC16
   - người/thời gian xác nhận
   - từ chối + lý do
   - trạng thái thanh toán
   - tổng phí phát sinh
   ===================================================================== */

IF COL_LENGTH('dbo.RentalOrders', 'ConfirmedByUserId') IS NULL
    ALTER TABLE dbo.RentalOrders ADD ConfirmedByUserId INT NULL;
IF COL_LENGTH('dbo.RentalOrders', 'ConfirmedAt') IS NULL
    ALTER TABLE dbo.RentalOrders ADD ConfirmedAt DATETIME2 NULL;
IF COL_LENGTH('dbo.RentalOrders', 'RejectedByUserId') IS NULL
    ALTER TABLE dbo.RentalOrders ADD RejectedByUserId INT NULL;
IF COL_LENGTH('dbo.RentalOrders', 'RejectedAt') IS NULL
    ALTER TABLE dbo.RentalOrders ADD RejectedAt DATETIME2 NULL;
IF COL_LENGTH('dbo.RentalOrders', 'RejectionReason') IS NULL
    ALTER TABLE dbo.RentalOrders ADD RejectionReason NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.RentalOrders', 'PaymentStatus') IS NULL
    ALTER TABLE dbo.RentalOrders ADD PaymentStatus NVARCHAR(20) NOT NULL
        CONSTRAINT DF_RentalOrders_PaymentStatus DEFAULT 'unpaid';
IF COL_LENGTH('dbo.RentalOrders', 'TotalExtraFee') IS NULL
    ALTER TABLE dbo.RentalOrders ADD TotalExtraFee DECIMAL(18,2) NOT NULL
        CONSTRAINT DF_RentalOrders_TotalExtraFee DEFAULT 0;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_RentalOrders_ConfirmedBy')
BEGIN
    ALTER TABLE dbo.RentalOrders WITH CHECK
    ADD CONSTRAINT FK_RentalOrders_ConfirmedBy FOREIGN KEY(ConfirmedByUserId) REFERENCES dbo.Users(Id);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name='FK_RentalOrders_RejectedBy')
BEGIN
    ALTER TABLE dbo.RentalOrders WITH CHECK
    ADD CONSTRAINT FK_RentalOrders_RejectedBy FOREIGN KEY(RejectedByUserId) REFERENCES dbo.Users(Id);
END
GO

-- Mở rộng trạng thái đơn: thêm rejected cho UC11.
DECLARE @StatusCheckName SYSNAME;
SELECT TOP 1 @StatusCheckName = cc.name
FROM sys.check_constraints cc
WHERE cc.parent_object_id = OBJECT_ID('dbo.RentalOrders')
  AND cc.parent_column_id = COLUMNPROPERTY(OBJECT_ID('dbo.RentalOrders'), 'Status', 'ColumnId');

IF @StatusCheckName IS NOT NULL AND @StatusCheckName <> 'CK_RentalOrders_Status_V2'
BEGIN
    EXEC('ALTER TABLE dbo.RentalOrders DROP CONSTRAINT ' + QUOTENAME(@StatusCheckName));
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_RentalOrders_Status_V2')
BEGIN
    ALTER TABLE dbo.RentalOrders
    ADD CONSTRAINT CK_RentalOrders_Status_V2
    CHECK (Status IN ('pending','confirmed','rejected','renting','completed','cancelled'));
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_RentalOrders_PaymentStatus')
BEGIN
    ALTER TABLE dbo.RentalOrders
    ADD CONSTRAINT CK_RentalOrders_PaymentStatus
    CHECK (PaymentStatus IN ('unpaid','partial','paid','refunded'));
END
GO

/* =====================================================================
   4. PHIẾU GIAO XE - UC13
   ===================================================================== */
IF OBJECT_ID('dbo.VehicleHandovers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.VehicleHandovers (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        OrderId INT NOT NULL UNIQUE,
        EmployeeId INT NOT NULL,
        HandoverAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleHandovers_HandoverAt DEFAULT GETDATE(),
        OdometerKm DECIMAL(18,2) NULL,
        FuelLevel NVARCHAR(50) NULL,
        VehicleCondition NVARCHAR(MAX) NULL,
        Notes NVARCHAR(MAX) NULL,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleHandovers_CreatedAt DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleHandovers_UpdatedAt DEFAULT GETDATE(),
        CONSTRAINT FK_VehicleHandovers_Order FOREIGN KEY(OrderId) REFERENCES dbo.RentalOrders(Id),
        CONSTRAINT FK_VehicleHandovers_Employee FOREIGN KEY(EmployeeId) REFERENCES dbo.Users(Id)
    );
END
GO

/* =====================================================================
   5. PHIẾU TRẢ XE - UC14
   ===================================================================== */
IF OBJECT_ID('dbo.VehicleReturns', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.VehicleReturns (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        OrderId INT NOT NULL UNIQUE,
        EmployeeId INT NOT NULL,
        ReturnedAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleReturns_ReturnedAt DEFAULT GETDATE(),
        OdometerKm DECIMAL(18,2) NULL,
        FuelLevel NVARCHAR(50) NULL,
        VehicleCondition NVARCHAR(MAX) NULL,
        NeedsMaintenance BIT NOT NULL CONSTRAINT DF_VehicleReturns_NeedsMaintenance DEFAULT 0,
        Notes NVARCHAR(MAX) NULL,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleReturns_CreatedAt DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_VehicleReturns_UpdatedAt DEFAULT GETDATE(),
        CONSTRAINT FK_VehicleReturns_Order FOREIGN KEY(OrderId) REFERENCES dbo.RentalOrders(Id),
        CONSTRAINT FK_VehicleReturns_Employee FOREIGN KEY(EmployeeId) REFERENCES dbo.Users(Id)
    );
END
GO

/* =====================================================================
   6. PHÍ PHÁT SINH - UC15
   - một phiếu trả/đơn có thể có nhiều khoản phí
   ===================================================================== */
IF OBJECT_ID('dbo.ExtraFees', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ExtraFees (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        OrderId INT NOT NULL,
        ReturnId INT NULL,
        FeeType NVARCHAR(50) NOT NULL,
        Amount DECIMAL(18,2) NOT NULL,
        Reason NVARCHAR(1000) NULL,
        CreatedByUserId INT NULL,
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_ExtraFees_CreatedAt DEFAULT GETDATE(),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_ExtraFees_UpdatedAt DEFAULT GETDATE(),
        CONSTRAINT FK_ExtraFees_Order FOREIGN KEY(OrderId) REFERENCES dbo.RentalOrders(Id),
        CONSTRAINT FK_ExtraFees_Return FOREIGN KEY(ReturnId) REFERENCES dbo.VehicleReturns(Id),
        CONSTRAINT FK_ExtraFees_CreatedBy FOREIGN KEY(CreatedByUserId) REFERENCES dbo.Users(Id),
        CONSTRAINT CK_ExtraFees_Amount CHECK (Amount >= 0),
        CONSTRAINT CK_ExtraFees_Type CHECK (FeeType IN ('late','damage','fuel','cleaning','other'))
    );
END
GO

/* Tự động tính lại tổng phí phát sinh của đơn thuê. */
CREATE OR ALTER TRIGGER dbo.TR_ExtraFees_RecalculateOrderTotal
ON dbo.ExtraFees
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH Affected AS (
        SELECT OrderId FROM inserted
        UNION
        SELECT OrderId FROM deleted
    )
    UPDATE o
       SET TotalExtraFee = ISNULL(x.TotalFee, 0),
           UpdatedAt = GETDATE()
    FROM dbo.RentalOrders o
    JOIN Affected a ON a.OrderId = o.Id
    OUTER APPLY (
        SELECT SUM(f.Amount) AS TotalFee
        FROM dbo.ExtraFees f
        WHERE f.OrderId = o.Id
    ) x;
END
GO

/* =====================================================================
   7. THANH TOÁN: UC09, UC16
   - bổ sung loại thanh toán phí phát sinh
   - tự động đồng bộ trạng thái thanh toán của đơn thuê
   ===================================================================== */
DECLARE @PaymentTypeCheck SYSNAME;
SELECT TOP 1 @PaymentTypeCheck = cc.name
FROM sys.check_constraints cc
WHERE cc.parent_object_id = OBJECT_ID('dbo.Payments')
  AND cc.parent_column_id = COLUMNPROPERTY(OBJECT_ID('dbo.Payments'), 'PaymentType', 'ColumnId');

IF @PaymentTypeCheck IS NOT NULL AND @PaymentTypeCheck <> 'CK_Payments_PaymentType_V2'
BEGIN
    EXEC('ALTER TABLE dbo.Payments DROP CONSTRAINT ' + QUOTENAME(@PaymentTypeCheck));
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_Payments_PaymentType_V2')
BEGIN
    ALTER TABLE dbo.Payments
    ADD CONSTRAINT CK_Payments_PaymentType_V2
    CHECK (PaymentType IN (
        'deposit','full_payment','late_fee','early_return_fee',
        'cancellation_fee','extra_fee','refund'
    ));
END
GO

CREATE OR ALTER TRIGGER dbo.TR_Payments_UpdateOrderPaymentStatus
ON dbo.Payments
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH Affected AS (
        SELECT OrderId FROM inserted
        UNION
        SELECT OrderId FROM deleted
    ), Paid AS (
        SELECT a.OrderId,
               ISNULL(SUM(CASE WHEN p.Status='completed' AND p.PaymentType <> 'refund' THEN p.Amount ELSE 0 END),0)
               - ISNULL(SUM(CASE WHEN p.Status='completed' AND p.PaymentType = 'refund' THEN p.Amount ELSE 0 END),0) AS NetPaid
        FROM Affected a
        LEFT JOIN dbo.Payments p ON p.OrderId=a.OrderId
        GROUP BY a.OrderId
    )
    UPDATE o
       SET PaymentStatus = CASE
            WHEN p.NetPaid <= 0 THEN 'unpaid'
            WHEN p.NetPaid >= o.TotalAmount THEN 'paid'
            ELSE 'partial'
           END,
           UpdatedAt = GETDATE()
    FROM dbo.RentalOrders o
    JOIN Paid p ON p.OrderId=o.Id;
END
GO

/* =====================================================================
   8. HỢP ĐỒNG - UC17
   ===================================================================== */
IF COL_LENGTH('dbo.Contracts', 'Status') IS NULL
BEGIN
    ALTER TABLE dbo.Contracts ADD Status NVARCHAR(20) NOT NULL
        CONSTRAINT DF_Contracts_Status DEFAULT 'draft';
END
GO

IF COL_LENGTH('dbo.Contracts', 'UpdatedAt') IS NULL
BEGIN
    ALTER TABLE dbo.Contracts ADD UpdatedAt DATETIME2 NOT NULL
        CONSTRAINT DF_Contracts_UpdatedAt DEFAULT GETDATE();
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_Contracts_Status')
BEGIN
    ALTER TABLE dbo.Contracts
    ADD CONSTRAINT CK_Contracts_Status CHECK (Status IN ('draft','active','completed','cancelled'));
END
GO

/* =====================================================================
   9. UC18 - KHÔNG CHO NGƯNG XE NẾU CÒN ĐƠN THUÊ HIỆU LỰC
   ===================================================================== */
CREATE OR ALTER TRIGGER dbo.TR_Cars_BlockSuspendWhenActiveRental
ON dbo.Cars
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF UPDATE(Status)
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM inserted i
            JOIN dbo.RentalOrders o ON o.CarId=i.Id
            WHERE i.Status='suspended'
              AND o.Status IN ('pending','confirmed','renting')
        )
        BEGIN
            ROLLBACK TRANSACTION;
            THROW 51010, N'Không thể ngưng hoạt động xe đang có đơn thuê hiệu lực.', 1;
        END
    END
END
GO

/* =====================================================================
   10. CHỐNG TRÙNG LỊCH AN TOÀN KHI 2 KHÁCH ĐẶT GẦN ĐỒNG THỜI
       UC05 + UC06 + yêu cầu xử lý đặt xe đồng thời

   Backend hiện tại đang kiểm tra trùng lịch rồi mới INSERT ở bước riêng.
   Cách này có thể xảy ra xung đột khi nhiều khách đặt cùng lúc.
   Nên chuyển API POST /orders sang gọi thủ tục sp_CreateRentalOrderSafe.
   ===================================================================== */
CREATE OR ALTER PROCEDURE dbo.sp_CreateRentalOrderSafe
    @OrderCode NVARCHAR(20),
    @CustomerId INT,
    @CarId INT,
    @StartDate DATETIME2,
    @EndDate DATETIME2,
    @BaseAmount DECIMAL(18,2),
    @TotalAmount DECIMAL(18,2),
    @DepositAmount DECIMAL(18,2),
    @Notes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @EndDate <= @StartDate
        THROW 51020, N'Thời gian trả phải lớn hơn thời gian nhận.', 1;

    BEGIN TRANSACTION;

    DECLARE @LockResult INT;
    EXEC @LockResult = sp_getapplock
        @Resource = CONCAT('CAR_RENTAL_BOOKING_', @CarId),
        @LockMode = 'Exclusive',
        @LockOwner = 'Transaction',
        @LockTimeout = 10000;

    IF @LockResult < 0
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51021, N'Không thể khóa lịch xe để đặt. Vui lòng thử lại.', 1;
    END

    IF NOT EXISTS (
        SELECT 1 FROM dbo.Cars WITH (UPDLOCK, HOLDLOCK)
        WHERE Id=@CarId AND Status IN ('available','booked')
    )
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51022, N'Xe không ở trạng thái có thể đặt thuê.', 1;
    END

    IF EXISTS (
        SELECT 1
        FROM dbo.RentalOrders WITH (UPDLOCK, HOLDLOCK)
        WHERE CarId=@CarId
          AND Status IN ('pending','confirmed','renting')
          AND StartDate < @EndDate
          AND EndDate > @StartDate
    )
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51023, N'Xe đã có lịch thuê trùng với khoảng thời gian yêu cầu.', 1;
    END

    INSERT INTO dbo.RentalOrders(
        OrderCode, CustomerId, CarId, StartDate, EndDate,
        BaseAmount, TotalAmount, DepositAmount, Notes, Status
    )
    VALUES(
        @OrderCode, @CustomerId, @CarId, @StartDate, @EndDate,
        @BaseAmount, @TotalAmount, @DepositAmount, @Notes, 'pending'
    );

    DECLARE @NewOrderId INT = SCOPE_IDENTITY();

    UPDATE dbo.Cars
       SET Status='booked', UpdatedAt=GETDATE()
     WHERE Id=@CarId AND Status='available';

    COMMIT TRANSACTION;

    SELECT * FROM dbo.RentalOrders WHERE Id=@NewOrderId;
END
GO

/* =====================================================================
   11. THỦ TỤC XÁC NHẬN / TỪ CHỐI ĐƠN - UC11/UC12
   ===================================================================== */
CREATE OR ALTER PROCEDURE dbo.sp_ConfirmRentalOrder
    @OrderId INT,
    @EmployeeId INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;

    DECLARE @CarId INT, @Start DATETIME2, @End DATETIME2, @CurrentStatus NVARCHAR(20);

    SELECT @CarId=CarId, @Start=StartDate, @End=EndDate, @CurrentStatus=Status
    FROM dbo.RentalOrders WITH (UPDLOCK, HOLDLOCK)
    WHERE Id=@OrderId;

    IF @CurrentStatus IS NULL
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51030, N'Không tìm thấy đơn thuê.', 1;
    END

    IF @CurrentStatus <> 'pending'
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51031, N'Chỉ đơn PENDING mới được xác nhận.', 1;
    END

    IF EXISTS (
        SELECT 1 FROM dbo.RentalOrders WITH (UPDLOCK, HOLDLOCK)
        WHERE CarId=@CarId
          AND Id<>@OrderId
          AND Status IN ('confirmed','renting')
          AND StartDate < @End
          AND EndDate > @Start
    )
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51032, N'Lịch xe phát sinh xung đột, không thể xác nhận.', 1;
    END

    UPDATE dbo.RentalOrders
       SET Status='confirmed',
           ConfirmedByUserId=@EmployeeId,
           ConfirmedAt=GETDATE(),
           UpdatedAt=GETDATE()
     WHERE Id=@OrderId;

    COMMIT TRANSACTION;
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_RejectRentalOrder
    @OrderId INT,
    @EmployeeId INT,
    @Reason NVARCHAR(1000)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NULLIF(LTRIM(RTRIM(@Reason)), '') IS NULL
        THROW 51040, N'Phải nhập lý do từ chối đơn.', 1;

    BEGIN TRANSACTION;

    DECLARE @CarId INT;
    SELECT @CarId = CarId
    FROM dbo.RentalOrders WITH (UPDLOCK, HOLDLOCK)
    WHERE Id=@OrderId AND Status='pending';

    IF @CarId IS NULL
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 51041, N'Chỉ đơn PENDING mới được từ chối.', 1;
    END

    UPDATE dbo.RentalOrders
       SET Status='rejected',
           RejectedByUserId=@EmployeeId,
           RejectedAt=GETDATE(),
           RejectionReason=@Reason,
           UpdatedAt=GETDATE()
     WHERE Id=@OrderId;

    -- Nếu xe không còn đơn thuê hiệu lực nào khác thì chuyển xe về trạng thái available.
    IF NOT EXISTS (
        SELECT 1 FROM dbo.RentalOrders
        WHERE CarId=@CarId
          AND Id<>@OrderId
          AND Status IN ('pending','confirmed','renting')
    )
    BEGIN
        UPDATE dbo.Cars
           SET Status='available', UpdatedAt=GETDATE()
         WHERE Id=@CarId AND Status='booked';
    END

    COMMIT TRANSACTION;
END
GO

/* =====================================================================
   12. CHỈ MỤC CHO CÁC BẢNG MỚI VÀ TRUY VẤN NGHIỆP VỤ
   ===================================================================== */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.CarImages') AND name='IX_CarImages_CarId')
    CREATE INDEX IX_CarImages_CarId ON dbo.CarImages(CarId);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.VehicleHandovers') AND name='IX_VehicleHandovers_EmployeeId')
    CREATE INDEX IX_VehicleHandovers_EmployeeId ON dbo.VehicleHandovers(EmployeeId);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.VehicleReturns') AND name='IX_VehicleReturns_EmployeeId')
    CREATE INDEX IX_VehicleReturns_EmployeeId ON dbo.VehicleReturns(EmployeeId);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.ExtraFees') AND name='IX_ExtraFees_OrderId')
    CREATE INDEX IX_ExtraFees_OrderId ON dbo.ExtraFees(OrderId);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.ExtraFees') AND name='IX_ExtraFees_ReturnId')
    CREATE INDEX IX_ExtraFees_ReturnId ON dbo.ExtraFees(ReturnId);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.RentalOrders') AND name='IX_RentalOrders_Car_Status_Dates')
    CREATE INDEX IX_RentalOrders_Car_Status_Dates
        ON dbo.RentalOrders(CarId, Status, StartDate, EndDate);
GO

/* =====================================================================
   13. VIEW THỐNG KÊ - BÁO CÁO - UC22
   Không cần lưu báo cáo thành bảng; dữ liệu được tổng hợp trực tiếp từ các bảng nghiệp vụ.
   ===================================================================== */
CREATE OR ALTER VIEW dbo.vw_OrderFinancialSummary
AS
SELECT
    o.Id AS OrderId,
    o.OrderCode,
    o.CustomerId,
    o.CarId,
    o.Status AS OrderStatus,
    o.PaymentStatus,
    o.BaseAmount,
    o.LateFee,
    o.EarlyReturnFee,
    o.CancellationFee,
    o.TotalExtraFee,
    o.TotalAmount,
    ISNULL(p.TotalPaid,0) AS TotalPaid,
    CASE WHEN o.TotalAmount - ISNULL(p.TotalPaid,0) > 0
         THEN o.TotalAmount - ISNULL(p.TotalPaid,0)
         ELSE 0 END AS RemainingAmount,
    o.CreatedAt
FROM dbo.RentalOrders o
OUTER APPLY (
    SELECT
       ISNULL(SUM(CASE WHEN Status='completed' AND PaymentType <> 'refund' THEN Amount ELSE 0 END),0)
       - ISNULL(SUM(CASE WHEN Status='completed' AND PaymentType = 'refund' THEN Amount ELSE 0 END),0) AS TotalPaid
    FROM dbo.Payments p
    WHERE p.OrderId=o.Id
) p;
GO

CREATE OR ALTER VIEW dbo.vw_CarRentalStatistics
AS
SELECT
    c.Id AS CarId,
    c.Name AS CarName,
    c.LicensePlate,
    c.Status AS CarStatus,
    COUNT(o.Id) AS TotalOrders,
    SUM(CASE WHEN o.Status='completed' THEN 1 ELSE 0 END) AS CompletedOrders,
    ISNULL(SUM(CASE WHEN o.Status='completed' THEN o.TotalAmount ELSE 0 END),0) AS CompletedRevenue
FROM dbo.Cars c
LEFT JOIN dbo.RentalOrders o ON o.CarId=c.Id
GROUP BY c.Id, c.Name, c.LicensePlate, c.Status;
GO

PRINT N'============================================================';
PRINT N'Đã hoàn tất nâng cấp CarRentalDB phiên bản V2.';
PRINT N'Đã bổ sung phân quyền, loại/ảnh xe, giao - trả xe, phí phát sinh,';
PRINT N'xác nhận/từ chối đơn, trạng thái thanh toán, thống kê - báo cáo và chống đặt trùng đồng thời.';
PRINT N'============================================================';
GO
