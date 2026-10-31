const sql = require("mssql");
const TABLES = [
  "Users",
  "Cars",
  "RentalOrders",
  "Payments",
  "Contracts",
  "Notifications",
  "AuditLogs",
  "VehicleHandovers",
  "VehicleReturns",
  "ExtraFees",
];
function config() {
  return {
    server: process.env.DB_SERVER || "localhost",
    database: process.env.DB_DATABASE || "CarRentalDB",
    user: process.env.DB_USER || "sa",
    password: process.env.DB_PASSWORD || "",
    port: Number(process.env.DB_PORT || 1433),
    options: {
      encrypt: process.env.DB_ENCRYPT !== "false",
      trustServerCertificate:
        process.env.DB_TRUST_SERVER_CERTIFICATE === "true",
      enableArithAbort: true,
    },
    pool: { max: 10, min: 0, idleTimeoutMillis: 30000 },
    connectionTimeout: 15000,
  };
}
function table(name) {
  if (!TABLES.includes(name)) throw Error("Unknown table");
  return `[dbo].[${name}]`;
}
class SqlContext {
  constructor(connection) {
    this.connection = connection;
  }
  request() {
    return new sql.Request(this.connection);
  }
  async list(name) {
    return (await this.request().query(`SELECT * FROM ${table(name)}`))
      .recordset;
  }
  async get(name, id) {
    return (
      await this.request()
        .input("id", sql.Int, id)
        .query(`SELECT * FROM ${table(name)} WHERE Id=@id`)
    ).recordset[0];
  }
  bind(request, values) {
    return Object.entries(values).map(([key, value], i) => {
      if (!/^[A-Za-z][A-Za-z0-9]*$/.test(key)) throw Error("Invalid column");
      const parameter = `p${i}`;
      if (value instanceof Date) request.input(parameter, sql.DateTime2, value);
      else if (typeof value === "boolean")
        request.input(parameter, sql.Bit, value);
      else if (typeof value === "number")
        request.input(parameter, sql.Decimal(18, 2), value);
      else
        request.input(
          parameter,
          sql.NVarChar(sql.MAX),
          value == null ? null : String(value),
        );
      return { key, parameter };
    });
  }
  async insert(name, values) {
    const request = this.request(),
      fields = this.bind(request, values);
    // OUTPUT INTO supports SQL Server tables with enabled triggers (the supplied V2 schema).
    const result = await request.query(
      `DECLARE @ids TABLE (Id INT); INSERT INTO ${table(name)} (${fields.map((f) => `[${f.key}]`).join(",")}) OUTPUT INSERTED.Id INTO @ids VALUES (${fields.map((f) => `@${f.parameter}`).join(",")}); SELECT t.* FROM ${table(name)} t JOIN @ids i ON t.Id=i.Id;`,
    );
    return result.recordset[0];
  }
  async update(name, id, values) {
    const request = this.request().input("id", sql.Int, id),
      fields = this.bind(request, values);
    await request.query(
      `UPDATE ${table(name)} SET ${fields.map((f) => `[${f.key}]=@${f.parameter}`).join(",")} WHERE Id=@id`,
    );
    return this.get(name, id);
  }
}
class SqlStore extends SqlContext {
  constructor(pool) {
    super(pool);
    this.pool = pool;
    this.kind = "sqlserver";
  }
  async transaction(fn) {
    const transaction = new sql.Transaction(this.pool);
    await transaction.begin(sql.ISOLATION_LEVEL.SERIALIZABLE);
    try {
      const lock = await new sql.Request(transaction).query(
        `DECLARE @r INT; EXEC @r=sys.sp_getapplock @Resource=N'CarRental:domain-write:v1', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=15000; SELECT @r AS Result;`,
      );
      if (lock.recordset[0].Result < 0)
        throw Object.assign(Error("Hệ thống đang bận, vui lòng thử lại"), {
          status: 503,
        });
      const value = await fn(new SqlContext(transaction));
      await transaction.commit();
      return value;
    } catch (error) {
      try {
        await transaction.rollback();
      } catch {}
      throw error;
    }
  }
  async health() {
    await this.pool.request().query("SELECT 1 AS healthy");
    return true;
  }
  async close() {
    await this.pool.close();
  }
}
async function connectStore() {
  return new SqlStore(await new sql.ConnectionPool(config()).connect());
}
module.exports = { SqlStore, SqlContext, connectStore, config, TABLES };
