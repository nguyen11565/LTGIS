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
