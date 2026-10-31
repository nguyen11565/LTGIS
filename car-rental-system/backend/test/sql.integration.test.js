require("dotenv").config();
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { randomBytes, randomUUID } = require("node:crypto");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const sql = require("mssql");
const request = require("supertest");
const { SqlStore, config } = require("../storage/sql");
const { createApp } = require("../app");
const exec = promisify(execFile);

// Opt-in only: needs a reachable SQL Server account with CREATE/DROP DATABASE.
// No existing database is migrated, seeded, truncated, or dropped by this test.
test(
  "SQL-01: migrations, repeatable seed, independent SQL transactions and persisted rental lifecycle",
  {
    skip:
      process.env.RUN_SQL_TESTS !== "1"
        ? "Set RUN_SQL_TESTS=1 with SQL Server credentials to execute real database integration"
        : false,
    timeout: 180000,
  },
  async () => {
    const name = `CarRentalTest_${randomBytes(12).toString("hex")}`;
    assert.match(name, /^CarRentalTest_[a-f0-9]{24}$/);
    const options = config();
    const master = await new sql.ConnectionPool({
      ...options,
      database: "master",
    }).connect();
    let created = false;
    const pools = [];
    try {
      await master.request().query(`CREATE DATABASE [${name}]`);
      created = true;
      const env = {
        ...process.env,
        DB_DATABASE: name,
        ALLOW_DEMO_SEED: "true",
      };
      const cwd = path.join(__dirname, "..");
      async function script(file) {
        await exec(process.execPath, [file], {
          cwd,
          env,
          timeout: 60000,
          maxBuffer: 1024 * 1024,
        });
      }
      await script("scripts/migrate.js");
      await script("scripts/migrate.js"); // Reapplying schema must preserve data and remain valid.
      await script("seed.js");
      await script("seed.js"); // Idempotent seed must not duplicate accounts or vehicles.
      const poolA = await new sql.ConnectionPool({
        ...options,
        database: name,
      }).connect();
      pools.push(poolA);
      const poolB = await new sql.ConnectionPool({
        ...options,
        database: name,
      }).connect();
      pools.push(poolB);
      const storeA = new SqlStore(poolA),
        storeB = new SqlStore(poolB);
      assert.equal((await storeA.list("Users")).length, 4);
      assert.equal((await storeA.list("Cars")).length, 7);
      let current = new Date("2030-01-01T00:00:00Z");
      const opts = {
        jwtSecret: "sql-integration-test-secret-at-least-32-chars",
        clock: () => new Date(current),
      };
      const apiA = request(createApp({ ...opts, store: storeA })),
        apiB = request(createApp({ ...opts, store: storeB }));
      const tokens = {};
      for (const [username, password, api] of [
        ["customer", "Customer@123", apiA],
        ["customer2", "Customer@123", apiB],
        ["employee", "Employee@123", apiA],
      ]) {
        const result = await api
          .post("/api/auth/login")
          .send({ username, password });
        assert.equal(result.status, 200, JSON.stringify(result.body));
        tokens[username] = result.body.data.token;
      }
      function send(api, who, method, url, body) {
        const r = api[method](`/api${url}`).set(
          "Authorization",
          `Bearer ${tokens[who]}`,
        );
        return body === undefined ? r : r.send(body);
      }
      function ok(r, status = 200) {
        assert.equal(r.status, status, JSON.stringify(r.body));
        assert.equal(r.body.success, true);
        return r.body.data;
      }
      const cars = ok(await apiA.get("/api/cars"));
      const car = cars.find((c) => c.Status === "available");
      assert.ok(car);
      const startDate = "2030-01-02T00:00:00Z",
        endDate = "2030-01-04T00:00:00Z";
      const booking = {
        carId: car.Id,
        startDate,
        endDate,
        notes: "SQL integration — isolated test DB",
      };
      const results = await Promise.all([
        send(apiA, "customer", "post", "/orders", booking),
        send(apiB, "customer2", "post", "/orders", booking),
      ]);
      assert.deepEqual(results.map((r) => r.status).sort(), [201, 409]);
      const index = results.findIndex((r) => r.status === 201),
        api = index === 0 ? apiA : apiB,
        who = index === 0 ? "customer" : "customer2";
      const order = results[index].body.data;
      assert.equal((await storeA.list("RentalOrders")).length, 1);
      assert.equal(
        (await storeB.get("RentalOrders", order.Id)).Status,
        "pending",
      );
      ok(
        await send(apiA, "employee", "put", `/orders/${order.Id}/confirm`, {}),
      );
      const payment = {
        orderId: order.Id,
        amount: Number(order.DepositAmount),
        paymentType: "deposit",
        method: "simulation",
        idempotencyKey: randomUUID(),
      };
      const paid = await Promise.all([
        send(apiA, who, "post", "/payments", payment),
        send(apiB, who, "post", "/payments", payment),
      ]);
      assert.ok(
        paid.every((r) => [200, 201].includes(r.status)),
        JSON.stringify(paid.map((r) => r.body)),
      );
      assert.equal((await storeA.list("Payments")).length, 1);
      current = new Date(startDate);
      ok(
        await send(apiA, "employee", "put", `/orders/${order.Id}/pickup`, {
          actualPickupDate: startDate,
          condition: "Nguyên vẹn",
          odometerKm: 10000,
          fuelLevel: "100%",
        }),
      );
      current = new Date("2030-01-04T01:00:00Z");
      ok(
        await send(apiA, "employee", "put", `/orders/${order.Id}/return`, {
          actualReturnDate: current.toISOString(),
          condition: "Nguyên vẹn",
          odometerKm: 10400,
          fuelLevel: "80%",
          extraFees: [
            {
              type: "fuel",
              amount: 100000,
              reason: "Bù nhiên liệu theo biên bản",
            },
          ],
        }),
      );
      const returned = ok(await send(api, who, "get", `/orders/${order.Id}`));
      assert.equal(
        Number(returned.LateFee),
        Math.round(Number(car.DailyRate) * 1.5),
      );
      assert.equal(
        Number(returned.TotalAmount),
        Number(order.BaseAmount) + Number(returned.LateFee) + 100000,
      );
      ok(
        await send(api, who, "post", "/payments", {
          orderId: order.Id,
          amount: Number(returned.BalanceDue),
          paymentType: "full_payment",
          method: "simulation",
          idempotencyKey: randomUUID(),
        }),
      );
      ok(
        await send(apiA, "employee", "put", `/orders/${order.Id}/complete`, {}),
      );
      const persisted = await storeB.get("RentalOrders", order.Id);
      assert.equal(persisted.Status, "completed");
      assert.equal(persisted.PaymentStatus, "paid");
      assert.equal((await storeB.list("VehicleHandovers")).length, 1);
      assert.equal((await storeB.list("VehicleReturns")).length, 1);
      assert.equal((await storeB.list("Contracts"))[0].Status, "completed");
      assert.equal((await storeB.get("Cars", car.Id)).Status, "available");
      assert.ok((await storeB.list("AuditLogs")).length >= 6);
      assert.ok((await storeB.list("Notifications")).length >= 6);
    } finally {
      await Promise.allSettled(pools.map((pool) => pool.close()));
      try {
        if (created) {
          // name is generated in this function, validated, and never read from user input.
          await master
            .request()
            .query(
              `ALTER DATABASE [${name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [${name}];`,
            );
        }
      } finally {
        await master.close();
      }
    }
  },
);
