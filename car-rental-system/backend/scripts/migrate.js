require("dotenv").config();
const fs = require("node:fs");
const path = require("node:path");
const sql = require("mssql");
const { config } = require("../storage/sql");
async function migrate() {
  const options = config(),
    name = options.database;
  if (!/^[A-Za-z][A-Za-z0-9_]{0,100}$/.test(name))
    throw Error("DB_DATABASE chỉ gồm chữ, số và dấu gạch dưới");
  let pool;
  try {
    pool = await new sql.ConnectionPool(options).connect();
  } catch (error) {
    const number = error.number || error.originalError?.info?.number;
    if (number !== 4060 && !/Cannot open database/i.test(error.message))
      throw error;
    const master = await new sql.ConnectionPool({
      ...options,
      database: "master",
    }).connect();
    try {
      await master
        .request()
        .query(`IF DB_ID(N'${name}') IS NULL CREATE DATABASE [${name}];`);
    } finally {
      await master.close();
    }
    pool = await new sql.ConnectionPool(options).connect();
  }
  try {
    for (const file of ["CarRentalDB.sql"]) {
      const content = fs.readFileSync(
        path.join(__dirname, "../../database", file),
        "utf8",
      );
      const tx = new sql.Transaction(pool);
      await tx.begin();
      try {
        for (const batch of content.split(/^\s*GO\s*(?:--.*)?$/gim)) {
          if (batch.trim()) await new sql.Request(tx).batch(batch);
        }
        await tx.commit();
        console.log(`Applied ${file}`);
      } catch (error) {
        try {
          await tx.rollback();
        } catch {}
        throw error;
      }
    }
  } finally {
    await pool.close();
  }
}
if (require.main === module)
  migrate().catch((e) => {
    console.error("Migration failed:", e.message);
    process.exit(1);
  });
module.exports = { migrate };
