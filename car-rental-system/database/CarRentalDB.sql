/*
   CSDL DAT THUE XE DU LICH - FILE CAI DAT GOP

   Thu tu noi dung: schema goc -> cac bo sung runtime.
   Cach chay bang SSMS:
     1. Tao database neu chua co (vi du CarRentalDB).
     2. Chon DUNG database tren thanh cong cu SSMS, roi mo file nay va nhan F5.
     3. Them tai khoan/xe mau: chay npm run db:seed tai thu muc du an.

   Cach chay tu Node.js: npm run db:migrate (dung DB_DATABASE trong backend/.env).
   File khong co USE/CREATE DATABASE de ho tro database tuy chinh.
   Giu nguyen cac dau GO; khong chay tren master/model/msdb/tempdb.
*/

/* Base schema, safe for a new or existing CarRentalDB. Use the selected database.
   Never drops or truncates data. Existing V2 installations are upgraded by 002_runtime.sql. */
IF OBJECT_ID('dbo.Users','U') IS NULL
CREATE TABLE dbo.Users (
 Id INT IDENTITY PRIMARY KEY, Username NVARCHAR(50) NOT NULL UNIQUE, PasswordHash NVARCHAR(255) NOT NULL,
 FullName NVARCHAR(100) NOT NULL, Email NVARCHAR(100) NOT NULL UNIQUE, Phone NVARCHAR(20) NULL,
 Address NVARCHAR(255) NULL, Role NVARCHAR(20) NOT NULL DEFAULT 'customer' CHECK (Role IN ('customer','employee','admin')),
 IsActive BIT NOT NULL DEFAULT 1, CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.Cars','U') IS NULL
CREATE TABLE dbo.Cars (
 Id INT IDENTITY PRIMARY KEY, Name NVARCHAR(100) NOT NULL, Brand NVARCHAR(50) NOT NULL, Model NVARCHAR(50) NULL,
 Year INT NOT NULL, Seats INT NOT NULL, Transmission NVARCHAR(20) NOT NULL, FuelType NVARCHAR(20) NOT NULL,
 DailyRate DECIMAL(18,2) NOT NULL CHECK (DailyRate>0), DepositRate DECIMAL(5,2) NOT NULL DEFAULT 30,
 LicensePlate NVARCHAR(20) NOT NULL UNIQUE, ImageUrl NVARCHAR(500) NULL, Description NVARCHAR(MAX) NULL,
 Status NVARCHAR(20) NOT NULL DEFAULT 'available' CHECK (Status IN ('available','booked','renting','maintenance','suspended')),
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.RentalOrders','U') IS NULL
CREATE TABLE dbo.RentalOrders (
 Id INT IDENTITY PRIMARY KEY, OrderCode NVARCHAR(20) NOT NULL UNIQUE, CustomerId INT NOT NULL REFERENCES dbo.Users(Id), CarId INT NOT NULL REFERENCES dbo.Cars(Id),
 StartDate DATETIME2 NOT NULL, EndDate DATETIME2 NOT NULL, ActualPickupDate DATETIME2 NULL, ActualReturnDate DATETIME2 NULL,
 PickupCondition NVARCHAR(MAX) NULL, ReturnCondition NVARCHAR(MAX) NULL,
 Status NVARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (Status IN ('pending','confirmed','rejected','renting','completed','cancelled')),
 PaymentStatus NVARCHAR(20) NOT NULL DEFAULT 'unpaid' CHECK (PaymentStatus IN ('unpaid','partial','paid','refunded')),
 BookedDailyRate DECIMAL(18,2) NOT NULL, BaseAmount DECIMAL(18,2) NOT NULL, TotalAmount DECIMAL(18,2) NOT NULL, DepositAmount DECIMAL(18,2) NOT NULL,
 LateFee DECIMAL(18,2) NOT NULL DEFAULT 0, EarlyReturnFee DECIMAL(18,2) NOT NULL DEFAULT 0, CancellationFee DECIMAL(18,2) NOT NULL DEFAULT 0, TotalExtraFee DECIMAL(18,2) NOT NULL DEFAULT 0,
 Notes NVARCHAR(MAX) NULL, CancellationReason NVARCHAR(1000) NULL, ConfirmedByUserId INT NULL REFERENCES dbo.Users(Id), ConfirmedAt DATETIME2 NULL,
 RejectedByUserId INT NULL REFERENCES dbo.Users(Id), RejectedAt DATETIME2 NULL, RejectionReason NVARCHAR(1000) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), CHECK (EndDate>StartDate)
);
GO
IF OBJECT_ID('dbo.Payments','U') IS NULL
CREATE TABLE dbo.Payments (
 Id INT IDENTITY PRIMARY KEY, OrderId INT NOT NULL REFERENCES dbo.RentalOrders(Id), Amount DECIMAL(18,2) NOT NULL CHECK (Amount>0),
 PaymentType NVARCHAR(30) NOT NULL CHECK (PaymentType IN ('deposit','full_payment','late_fee','early_return_fee','cancellation_fee','extra_fee','refund')),
 PaymentMethod NVARCHAR(30) NOT NULL, Status NVARCHAR(20) NOT NULL CHECK (Status IN ('pending','completed','failed')),
 TransactionCode NVARCHAR(100) NOT NULL UNIQUE, TransactionRef NVARCHAR(100) NULL, IdempotencyKey NVARCHAR(100) NULL, RequestFingerprint NVARCHAR(64) NULL,
 CreatedByUserId INT NULL REFERENCES dbo.Users(Id), Notes NVARCHAR(MAX) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.Contracts','U') IS NULL
CREATE TABLE dbo.Contracts (
 Id INT IDENTITY PRIMARY KEY, OrderId INT NOT NULL UNIQUE REFERENCES dbo.RentalOrders(Id), ContractCode NVARCHAR(50) NOT NULL UNIQUE,
 ContractNumber NVARCHAR(50) NULL, CustomerName NVARCHAR(100) NULL, CustomerPhone NVARCHAR(20) NULL, CustomerEmail NVARCHAR(100) NULL, CarInfo NVARCHAR(500) NULL, TotalAmount DECIMAL(18,2) NULL, DepositAmount DECIMAL(18,2) NULL, RentalTerms NVARCHAR(MAX) NULL,
 Content NVARCHAR(MAX) NOT NULL, Status NVARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (Status IN ('draft','active','completed','cancelled')),
 SignedAt DATETIME2 NULL, CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.Notifications','U') IS NULL
CREATE TABLE dbo.Notifications (
 Id INT IDENTITY PRIMARY KEY, UserId INT NOT NULL REFERENCES dbo.Users(Id), OrderId INT NULL REFERENCES dbo.RentalOrders(Id), Type NVARCHAR(50) NOT NULL,
 Title NVARCHAR(200) NOT NULL, Message NVARCHAR(MAX) NOT NULL, IsRead BIT NOT NULL DEFAULT 0, CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.AuditLogs','U') IS NULL
CREATE TABLE dbo.AuditLogs (
 Id INT IDENTITY PRIMARY KEY, UserId INT NULL REFERENCES dbo.Users(Id), Username NVARCHAR(50) NULL, Action NVARCHAR(100) NOT NULL,
 EntityType NVARCHAR(50) NOT NULL, EntityId INT NULL, OldValue NVARCHAR(MAX) NULL, NewValue NVARCHAR(MAX) NULL,
 IpAddress NVARCHAR(50) NULL, CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.VehicleHandovers','U') IS NULL
CREATE TABLE dbo.VehicleHandovers (
 Id INT IDENTITY PRIMARY KEY, OrderId INT NOT NULL UNIQUE REFERENCES dbo.RentalOrders(Id), EmployeeId INT NOT NULL REFERENCES dbo.Users(Id),
 HandoverAt DATETIME2 NOT NULL, OdometerKm DECIMAL(18,2) NULL, FuelLevel NVARCHAR(50) NULL, VehicleCondition NVARCHAR(MAX) NULL, Notes NVARCHAR(MAX) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.VehicleReturns','U') IS NULL
CREATE TABLE dbo.VehicleReturns (
 Id INT IDENTITY PRIMARY KEY, OrderId INT NOT NULL UNIQUE REFERENCES dbo.RentalOrders(Id), EmployeeId INT NOT NULL REFERENCES dbo.Users(Id),
 ReturnedAt DATETIME2 NOT NULL, OdometerKm DECIMAL(18,2) NULL, FuelLevel NVARCHAR(50) NULL, VehicleCondition NVARCHAR(MAX) NULL, NeedsMaintenance BIT NOT NULL DEFAULT 0, Notes NVARCHAR(MAX) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('dbo.ExtraFees','U') IS NULL
CREATE TABLE dbo.ExtraFees (
 Id INT IDENTITY PRIMARY KEY, OrderId INT NOT NULL REFERENCES dbo.RentalOrders(Id), ReturnId INT NULL REFERENCES dbo.VehicleReturns(Id),
 FeeType NVARCHAR(50) NOT NULL CHECK (FeeType IN ('late','damage','fuel','cleaning','other')), Amount DECIMAL(18,2) NOT NULL CHECK(Amount>=0),
 Reason NVARCHAR(1000) NULL, CreatedByUserId INT NULL REFERENCES dbo.Users(Id),
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(), UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

/* Additive application migration after the supplied V2 or base schema.
   Keep DatThueXeDuLich.sql unchanged as the user's original reference. */
IF COL_LENGTH('dbo.Users','Address') IS NULL ALTER TABLE dbo.Users ADD Address NVARCHAR(255) NULL;
IF COL_LENGTH('dbo.Cars','DepositRate') IS NULL ALTER TABLE dbo.Cars ADD DepositRate DECIMAL(5,2) NOT NULL CONSTRAINT DF_Cars_DepositRate_App DEFAULT 30;
IF COL_LENGTH('dbo.RentalOrders','BookedDailyRate') IS NULL ALTER TABLE dbo.RentalOrders ADD BookedDailyRate DECIMAL(18,2) NULL;
GO
-- Preserve historical price from the booked total rather than current car price.
UPDATE dbo.RentalOrders SET BookedDailyRate=ROUND(BaseAmount / CASE WHEN CEILING(DATEDIFF_BIG(SECOND,StartDate,EndDate)/86400.0)<1 THEN 1 ELSE CEILING(DATEDIFF_BIG(SECOND,StartDate,EndDate)/86400.0) END,0) WHERE BookedDailyRate IS NULL;
GO
IF COL_LENGTH('dbo.RentalOrders','CancellationReason') IS NULL ALTER TABLE dbo.RentalOrders ADD CancellationReason NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.RentalOrders','PaymentStatus') IS NULL ALTER TABLE dbo.RentalOrders ADD PaymentStatus NVARCHAR(20) NOT NULL CONSTRAINT DF_Order_PaymentStatus_App DEFAULT 'unpaid';
IF COL_LENGTH('dbo.RentalOrders','TotalExtraFee') IS NULL ALTER TABLE dbo.RentalOrders ADD TotalExtraFee DECIMAL(18,2) NOT NULL CONSTRAINT DF_Order_Extra_App DEFAULT 0;
IF COL_LENGTH('dbo.RentalOrders','ConfirmedByUserId') IS NULL ALTER TABLE dbo.RentalOrders ADD ConfirmedByUserId INT NULL;
IF COL_LENGTH('dbo.RentalOrders','ConfirmedAt') IS NULL ALTER TABLE dbo.RentalOrders ADD ConfirmedAt DATETIME2 NULL;
IF COL_LENGTH('dbo.RentalOrders','RejectedByUserId') IS NULL ALTER TABLE dbo.RentalOrders ADD RejectedByUserId INT NULL;
IF COL_LENGTH('dbo.RentalOrders','RejectedAt') IS NULL ALTER TABLE dbo.RentalOrders ADD RejectedAt DATETIME2 NULL;
IF COL_LENGTH('dbo.RentalOrders','RejectionReason') IS NULL ALTER TABLE dbo.RentalOrders ADD RejectionReason NVARCHAR(1000) NULL;
IF COL_LENGTH('dbo.Payments','IdempotencyKey') IS NULL ALTER TABLE dbo.Payments ADD IdempotencyKey NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Payments','RequestFingerprint') IS NULL ALTER TABLE dbo.Payments ADD RequestFingerprint NVARCHAR(64) NULL;
IF COL_LENGTH('dbo.Payments','CreatedByUserId') IS NULL ALTER TABLE dbo.Payments ADD CreatedByUserId INT NULL;
IF COL_LENGTH('dbo.Payments','UpdatedAt') IS NULL ALTER TABLE dbo.Payments ADD UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_Payments_UpdatedAt_App DEFAULT SYSUTCDATETIME();
IF COL_LENGTH('dbo.Contracts','Status') IS NULL ALTER TABLE dbo.Contracts ADD Status NVARCHAR(20) NOT NULL CONSTRAINT DF_Contracts_Status_App DEFAULT 'draft';
IF COL_LENGTH('dbo.Contracts','UpdatedAt') IS NULL ALTER TABLE dbo.Contracts ADD UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_Contracts_UpdatedAt_App DEFAULT SYSUTCDATETIME();
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.Users') AND name='UX_Users_Phone') AND NOT EXISTS (SELECT Phone FROM dbo.Users WHERE Phone IS NOT NULL GROUP BY Phone HAVING COUNT(*)>1)
CREATE UNIQUE INDEX UX_Users_Phone ON dbo.Users(Phone) WHERE Phone IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.Payments') AND name='UX_Payments_IdempotencyKey')
CREATE UNIQUE INDEX UX_Payments_IdempotencyKey ON dbo.Payments(IdempotencyKey) WHERE IdempotencyKey IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.RentalOrders') AND name='IX_RentalOrders_Car_Status_Dates')
CREATE INDEX IX_RentalOrders_Car_Status_Dates ON dbo.RentalOrders(CarId,Status,StartDate,EndDate);
GO
IF COL_LENGTH('dbo.Payments','TransactionCode') IS NULL ALTER TABLE dbo.Payments ADD TransactionCode NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Payments','TransactionRef') IS NULL ALTER TABLE dbo.Payments ADD TransactionRef NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contracts','ContractCode') IS NULL ALTER TABLE dbo.Contracts ADD ContractCode NVARCHAR(50) NULL;
IF COL_LENGTH('dbo.Contracts','Content') IS NULL ALTER TABLE dbo.Contracts ADD Content NVARCHAR(MAX) NULL;
IF COL_LENGTH('dbo.Contracts','ContractNumber') IS NULL ALTER TABLE dbo.Contracts ADD ContractNumber NVARCHAR(50) NULL;
IF COL_LENGTH('dbo.Contracts','CustomerName') IS NULL ALTER TABLE dbo.Contracts ADD CustomerName NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contracts','CustomerPhone') IS NULL ALTER TABLE dbo.Contracts ADD CustomerPhone NVARCHAR(20) NULL;
IF COL_LENGTH('dbo.Contracts','CustomerEmail') IS NULL ALTER TABLE dbo.Contracts ADD CustomerEmail NVARCHAR(100) NULL;
IF COL_LENGTH('dbo.Contracts','CarInfo') IS NULL ALTER TABLE dbo.Contracts ADD CarInfo NVARCHAR(500) NULL;
IF COL_LENGTH('dbo.Contracts','TotalAmount') IS NULL ALTER TABLE dbo.Contracts ADD TotalAmount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.Contracts','DepositAmount') IS NULL ALTER TABLE dbo.Contracts ADD DepositAmount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.Contracts','RentalTerms') IS NULL ALTER TABLE dbo.Contracts ADD RentalTerms NVARCHAR(MAX) NULL;
GO
/* Preserve legacy single-column enumerations and add only the new application's
   explicit values. Compound predicates require a DBA review rather than silently
   weakening checks on other columns. This migration does not disable constraints. */
DECLARE @Extensions TABLE (TableName SYSNAME, ColumnName SYSNAME, AllowedSql NVARCHAR(MAX), Marker NVARCHAR(100));
INSERT INTO @Extensions VALUES
('RentalOrders','Status',N'''pending'',''confirmed'',''rejected'',''renting'',''completed'',''cancelled''',N'%rejected%'),
('Payments','PaymentMethod',N'''simulation''',N'%simulation%'),
('Payments','PaymentType',N'''deposit'',''full_payment'',''refund''',N'%refund%'),
('Notifications','Type',N'''order_created'',''order_confirmed'',''order_cancelled'',''car_picked_up'',''car_returned'',''order_completed'',''payment_failed'',''payment_refunded'',''payment_received'',''pickup_reminder'',''contract_updated''',N'%contract_updated%');
DECLARE @table SYSNAME,@column SYSNAME,@allowed NVARCHAR(MAX),@marker NVARCHAR(100),@constraint SYSNAME,@definition NVARCHAR(MAX),@sql NVARCHAR(MAX),@message NVARCHAR(2048);
DECLARE extension_cursor CURSOR LOCAL FAST_FORWARD FOR SELECT TableName,ColumnName,AllowedSql,Marker FROM @Extensions;
OPEN extension_cursor;
FETCH NEXT FROM extension_cursor INTO @table,@column,@allowed,@marker;
WHILE @@FETCH_STATUS=0
BEGIN
    DECLARE constraint_cursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT cc.name,cc.definition FROM sys.check_constraints cc
    WHERE cc.parent_object_id=OBJECT_ID(N'dbo.'+@table)
      AND (cc.parent_column_id=COLUMNPROPERTY(cc.parent_object_id,@column,'ColumnId') OR cc.definition LIKE N'%'+@column+N'%')
      AND cc.definition NOT LIKE @marker;
    OPEN constraint_cursor;
    FETCH NEXT FROM constraint_cursor INTO @constraint,@definition;
    WHILE @@FETCH_STATUS=0
    BEGIN
        IF EXISTS (
            SELECT 1 FROM sys.sql_expression_dependencies d
            WHERE d.referencing_id=OBJECT_ID(N'dbo.'+@constraint)
              AND d.referenced_id=OBJECT_ID(N'dbo.'+@table)
              AND d.referenced_minor_id>0
              AND d.referenced_minor_id<>COLUMNPROPERTY(OBJECT_ID(N'dbo.'+@table),@column,'ColumnId')
        )
        BEGIN
            SET @message=N'Cannot safely extend compound constraint '+@constraint+N'. Ask the database owner to allow the documented application values for '+@table+N'.'+@column+N', preserving its other predicates, then rerun migrate.';
            THROW 51040,@message,1;
        END
        SET @sql=N'ALTER TABLE dbo.'+QUOTENAME(@table)+N' DROP CONSTRAINT '+QUOTENAME(@constraint)+N'; ALTER TABLE dbo.'+QUOTENAME(@table)+N' WITH CHECK ADD CONSTRAINT '+QUOTENAME(@constraint)+N' CHECK (('+@definition+N') OR '+QUOTENAME(@column)+N' IN ('+@allowed+N'));';
        EXEC sys.sp_executesql @sql;
        FETCH NEXT FROM constraint_cursor INTO @constraint,@definition;
    END
    CLOSE constraint_cursor;
    DEALLOCATE constraint_cursor;
    FETCH NEXT FROM extension_cursor INTO @table,@column,@allowed,@marker;
END
CLOSE extension_cursor;
DEALLOCATE extension_cursor;
GO
/* A returned vehicle is physically free even while accounting is unsettled.
   Pending and confirmed bookings still prevent suspending the vehicle. */
CREATE OR ALTER TRIGGER dbo.TR_Cars_BlockSuspendWhenActiveRental
ON dbo.Cars
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(Status) AND EXISTS (
        SELECT 1 FROM inserted i
        JOIN dbo.RentalOrders o ON o.CarId=i.Id
        WHERE i.Status='suspended'
          AND o.Status IN ('pending','confirmed','renting')
          AND o.ActualReturnDate IS NULL
    )
    BEGIN
        THROW 51010,N'Cannot suspend a car with an active rental reservation.',1;
    END
END;
GO
