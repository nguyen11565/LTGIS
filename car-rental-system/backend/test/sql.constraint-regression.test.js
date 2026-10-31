require("dotenv").config();
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { randomBytes } = require("node:crypto");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const sql = require("mssql");
const { config } = require("../storage/sql");
const { migrate } = require("../scripts/migrate");
const exec = promisify(execFile);

// Requires an explicitly enabled real SQL Server, and touches only its own random DB.
test(
  "SQL-02: extending Status never rewrites PaymentStatus; real compound checks remain protected",
  {
    skip:
      process.env.RUN_SQL_TESTS !== "1"
        ? "Set RUN_SQL_TESTS=1 with SQL Server credentials to run the constraint regression"
        : false,
    timeout: 180000,
  },
  async () => {
    const name = `CarRentalTest_${randomBytes(12).toString("hex")}`;
    assert.match(name, /^CarRentalTest_[a-f0-9]{24}$/);
    const options = config();
    const originalDatabase = process.env.DB_DATABASE;
    const master = await new sql.ConnectionPool({
      ...options,
      database: "master",
    }).connect();
    let created = false;
    let pool;
    try {
      await master.request().query(`CREATE DATABASE [${name}]`);
      created = true;
      process.env.DB_DATABASE = name;
      // A new schema already has separate Status and PaymentStatus CHECKs.
      // The former substring filter fails here even before the legacy fixtures.
      await migrate();
      pool = await new sql.ConnectionPool({ ...options, database: name }).connect();
      await exec(process.execPath, ["seed.js"], {
        cwd: path.join(__dirname, ".."),
        env: { ...process.env, ALLOW_DEMO_SEED: "true" },
        timeout: 60000,
        maxBuffer: 1024 * 1024,
      });
      const initial = (await pool.request().query(`
        SELECT name, parent_column_id, definition
        FROM sys.check_constraints
        WHERE parent_object_id=OBJECT_ID(N'dbo.RentalOrders')
      `)).recordset;
      const columnIds = (await pool.request().query(`
        SELECT COLUMNPROPERTY(OBJECT_ID(N'dbo.RentalOrders'),N'Status','ColumnId') AS StatusId,
               COLUMNPROPERTY(OBJECT_ID(N'dbo.RentalOrders'),N'PaymentStatus','ColumnId') AS PaymentStatusId;
      `)).recordset[0];
      const originalStatus = initial.find(c => c.parent_column_id === columnIds.StatusId);
      const originalPayment = initial.find(c => c.parent_column_id === columnIds.PaymentStatusId);
      assert.ok(originalStatus, "Base schema has a column-level Status CHECK");
      assert.ok(originalPayment, "Base schema has a column-level PaymentStatus CHECK");
      const quote = value => "[" + value.replace(/]/g, "]]") + "]";
      // All identifiers here come from this test's own generated database.
      await pool.request().query(`
        ALTER TABLE dbo.RentalOrders DROP CONSTRAINT ${quote(originalStatus.name)};
        ALTER TABLE dbo.RentalOrders WITH CHECK ADD CONSTRAINT CK_Test_LegacyOrderStatus
          CHECK (Status IN ('pending','confirmed','renting','completed','cancelled'));
        ALTER TABLE dbo.RentalOrders WITH CHECK ADD CONSTRAINT CK_Test_StatusName_PaymentOnly
          CHECK (PaymentStatus IN ('unpaid','partial','paid','refunded'));
        INSERT INTO dbo.RentalOrders
          (OrderCode,CustomerId,CarId,StartDate,EndDate,BookedDailyRate,BaseAmount,TotalAmount,DepositAmount,Status,PaymentStatus)
        SELECT N'SQL-CHECK-FIXTURE',
          (SELECT TOP 1 Id FROM dbo.Users WHERE Role='customer' ORDER BY Id),
          (SELECT TOP 1 Id FROM dbo.Cars ORDER BY Id),
          '2030-01-02T00:00:00','2030-01-03T00:00:00',100,100,100,30,'pending','unpaid';
      `);
      async function paymentChecks() {
        return (await pool.request()
          .input("original", sql.NVarChar(128), originalPayment.name)
          .query(`SELECT name,definition,parent_column_id,is_disabled,is_not_trusted
                  FROM sys.check_constraints
                  WHERE parent_object_id=OBJECT_ID(N'dbo.RentalOrders')
                    AND name IN (@original,N'CK_Test_StatusName_PaymentOnly')
                  ORDER BY name;`)).recordset;
      }
      const before = await paymentChecks();
      assert.equal(before.length, 2);
      assert.ok(before.some(c => c.parent_column_id === 0), "Includes a table-level PaymentStatus CHECK");
      assert.ok(before.some(c => c.parent_column_id > 0), "Includes a column-level PaymentStatus CHECK");
      await migrate();
      await migrate(); // Also verifies the fixed upgrade remains repeatable.
      assert.deepEqual(await paymentChecks(), before, "PaymentStatus definitions and trust/enabled flags stay unchanged");
      await pool.request().query(`UPDATE dbo.RentalOrders SET Status='rejected' WHERE OrderCode=N'SQL-CHECK-FIXTURE';`);
      await assert.rejects(
        pool.request().query(`UPDATE dbo.RentalOrders SET PaymentStatus='invalid-test-value' WHERE OrderCode=N'SQL-CHECK-FIXTURE';`),
        error => error.number === 547,
        "Unrecognized payment status must still violate its original CHECK",
      );
      const preserved = (await pool.request().query(`SELECT Status,PaymentStatus,BaseAmount FROM dbo.RentalOrders WHERE OrderCode=N'SQL-CHECK-FIXTURE';`)).recordset;
      assert.equal(preserved[0].PaymentStatus, "unpaid");
      // This genuinely involves BOTH columns and must not be weakened by OR-ing
      // every supported Status into it. Its definition intentionally lacks rejected.
      await pool.request().query(`
        ALTER TABLE dbo.RentalOrders WITH CHECK ADD CONSTRAINT CK_Test_RealCompound
          CHECK (Status <> 'confirmed' OR PaymentStatus <> 'unpaid');
        ALTER TABLE dbo.Contracts DROP COLUMN RentalTerms;
      `);
      await assert.rejects(
        migrate(),
        error => error.number === 51040 || error.originalError?.info?.number === 51040,
        "A real multi-column CHECK must still require database-owner review",
      );
      const afterFailure = (await pool.request().query(`
        SELECT COL_LENGTH(N'dbo.Contracts',N'RentalTerms') AS RentalTermsLength;
        SELECT name,is_disabled,is_not_trusted FROM sys.check_constraints WHERE name=N'CK_Test_RealCompound';
        SELECT Status,PaymentStatus,BaseAmount FROM dbo.RentalOrders WHERE OrderCode=N'SQL-CHECK-FIXTURE';
      `)).recordsets;
      assert.equal(afterFailure[0][0].RentalTermsLength, null, "Earlier column addition was rolled back with the failed migration");
      assert.equal(afterFailure[1][0].is_disabled, false);
      assert.equal(afterFailure[1][0].is_not_trusted, false);
      assert.deepEqual(afterFailure[2], preserved, "Existing rental data remains unchanged");
      assert.deepEqual(await paymentChecks(), before);
    } finally {
      if (originalDatabase === undefined) delete process.env.DB_DATABASE;
      else process.env.DB_DATABASE = originalDatabase;
      if (pool) await pool.close();
      try {
        if (created) await master.request().query(`ALTER DATABASE [${name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [${name}];`);
      } finally {
        await master.close();
      }
    }
  },
);
