const { test, before } = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");
const { createApp } = require("../app");
const { createMemoryStore } = require("../storage/memory");
const { createDemoState } = require("../seedData");

// An explicit isolated adapter tests business behavior. Production always uses SQL Server.
const BASE = "2030-01-01T00:00:00.000Z";
const START = "2030-01-02T00:00:00.000Z";
const END = "2030-01-04T00:00:00.000Z";
let demo;
before(async () => {
  demo = { RentalOrders: [], ...(await createDemoState()) };
});

async function fixture() {
  let current = new Date(BASE);
  const store = createMemoryStore(demo);
  const app = createApp({
    store,
    jwtSecret: "isolated-test-secret-at-least-32-characters",
    clock: () => new Date(current),
  });
  const api = request(app);
  const tokens = {};
  for (const [username, password] of [
    ["admin", "Admin@123"],
    ["employee", "Employee@123"],
    ["customer", "Customer@123"],
    ["customer2", "Customer@123"],
  ]) {
    const res = await api.post("/api/auth/login").send({ username, password });
    assert.equal(res.status, 200, JSON.stringify(res.body));
    tokens[username] = res.body.data.token;
  }
  const send = (method, path, body, who = "customer") => {
    const req = api[method](`/api${path}`).set(
      "Authorization",
      `Bearer ${tokens[who]}`,
    );
    return body === undefined ? req : req.send(body);
  };
  const car = (await api.get("/api/cars/1")).body.data;
  const dailyRate = Number(car.DailyRate);
  async function book(body = {}, who = "customer") {
    return send(
      "post",
      "/orders",
      {
        carId: 1,
        startDate: START,
        endDate: END,
        notes: "Chuyến đi kiểm thử",
        ...body,
      },
      who,
    );
  }
  async function payment(order, body = {}, who = "customer") {
    return send(
      "post",
      "/payments",
      {
        orderId: order.Id,
        amount: Number(order.DepositAmount),
        paymentType: "deposit",
        method: "simulation",
        idempotencyKey: `test-${crypto.randomUUID()}`,
        ...body,
      },
      who,
    );
  }
  async function confirmed() {
    const booking = await book();
    assert.equal(booking.status, 201, JSON.stringify(booking.body));
    const order = booking.body.data;
    const confirmation = await send(
      "put",
      `/orders/${order.Id}/confirm`,
      {},
      "employee",
    );
    assert.equal(confirmation.status, 200, JSON.stringify(confirmation.body));
    return order;
  }
  async function renting() {
    const order = await confirmed();
    const paid = await payment(order);
    assert.ok([200, 201].includes(paid.status), JSON.stringify(paid.body));
    current = new Date(START);
    const pickup = await send(
      "put",
      `/orders/${order.Id}/pickup`,
      {
        actualPickupDate: START,
        condition: "Xe nguyên vẹn, đủ phụ kiện",
        odometerKm: 10000,
        fuelLevel: "100%",
        notes: "Đã đối chiếu giấy phép lái xe",
      },
      "employee",
    );
    assert.equal(pickup.status, 200, JSON.stringify(pickup.body));
    return order;
  }
  return {
    api,
    send,
    book,
    payment,
    confirmed,
    renting,
    store,
    car,
    dailyRate,
    advance(value) {
      current = new Date(value);
    },
  };
}
function denied(res, ...statuses) {
  assert.ok(
    statuses.includes(res.status),
    `Expected ${statuses}, got ${res.status}: ${JSON.stringify(res.body)}`,
  );
  assert.equal(res.body.success, false);
}
function ok(res, status = 200) {
  assert.equal(res.status, status, JSON.stringify(res.body));
  assert.equal(res.body.success, true);
  return res.body.data;
}

// Authentication and authorization are tested at the HTTP boundary, not only utility functions.
test("AUTH-01: customer registration cannot grant admin privileges; duplicates are rejected", async () => {
  const f = await fixture();
  const body = {
    username: "newtraveler",
    password: "Traveler@123",
    fullName: "Nguyễn Khách Mới",
    email: "newtraveler@example.com",
    phone: "0987654123",
    role: "admin",
    isActive: true,
  };
  const created = await f.api.post("/api/auth/register").send(body);
  assert.ok([200, 201].includes(created.status), JSON.stringify(created.body));
  const login = await f.api
    .post("/api/auth/login")
    .send({ username: body.username, password: body.password });
  assert.equal(ok(login).user.role, "customer");
  const forbidden = await f.api
    .get("/api/users")
    .set("Authorization", `Bearer ${login.body.data.token}`);
  denied(forbidden, 403);
  denied(await f.api.post("/api/auth/register").send(body), 400, 409);
});
test("AUTH-02: unauthenticated, invalid login, weak password and cross-account access are rejected", async () => {
  const f = await fixture();
  denied(await f.api.get("/api/orders"), 401);
  denied(
    await f.api
      .post("/api/auth/login")
      .send({ username: "customer", password: "wrong" }),
    401,
  );
  denied(
    await f.api
      .post("/api/auth/register")
      .send({
        username: "weakpassword",
        password: "x",
        fullName: "Khách",
        email: "weak@example.com",
        phone: "0981234123",
      }),
    400,
  );
  const order = ok(await f.book(), 201);
  denied(
    await f.send("get", `/orders/${order.Id}`, undefined, "customer2"),
    403,
    404,
  );
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/cancel`,
      { reason: "Không phải đơn của tôi" },
      "customer2",
    ),
    403,
    404,
  );
  denied(await f.payment(order, {}, "customer2"), 403, 404);
});
test("AUTH-03: disabled users lose access even with an existing token", async () => {
  const f = await fixture();
  ok(await f.send("put", "/users/4", { isActive: false }, "admin"));
  denied(await f.send("get", "/auth/me", undefined, "customer2"), 401, 403);
});
test("DATE-01: malformed, timezone-free, reversed and past booking dates produce no orders", async () => {
  const f = await fixture();
  for (const input of [
    { startDate: "not-a-date" },
    { startDate: "2030-01-02T10:00" },
    { startDate: END, endDate: START },
    { startDate: START, endDate: START },
    { startDate: "2029-12-31T00:00:00Z" },
  ]) {
    denied(await f.book(input), 400);
  }
  assert.equal(
    f.store.snapshot().RentalOrders.length,
    demo.RentalOrders.length,
  );
});
test("PRICE-01: quote rounds up each 24h and snapshots rate/deposit on the order", async () => {
  const f = await fixture();
  const endDate = "2030-01-03T00:01:00.000Z";
  const q = ok(
    await f.send("post", "/orders/quote", {
      carId: 1,
      startDate: START,
      endDate,
    }),
  );
  assert.equal(q.days, 2);
  assert.equal(q.baseAmount, f.dailyRate * 2);
  assert.equal(q.depositAmount, Math.round(q.baseAmount * 0.3));
  const order = ok(await f.book({ endDate }), 201);
  assert.equal(Number(order.BaseAmount), q.baseAmount);
  assert.equal(Number(order.DepositAmount), q.depositAmount);
  const editedCar = Object.fromEntries(
    [
      "Name",
      "Brand",
      "Model",
      "Year",
      "Seats",
      "Transmission",
      "FuelType",
      "DailyRate",
      "LicensePlate",
      "ImageUrl",
      "Description",
    ].map((key) => [key[0].toLowerCase() + key.slice(1), f.car[key]]),
  );
  ok(
    await f.send(
      "put",
      "/cars/1",
      { ...editedCar, dailyRate: f.dailyRate * 2 },
      "admin",
    ),
  );
  const saved = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(Number(saved.BaseAmount), q.baseAmount);
  assert.equal(Number(saved.DailyRate), f.dailyRate);
});
test("SCHEDULE-01: all overlapping interval shapes conflict; a boundary-adjacent rental succeeds", async () => {
  const f = await fixture();
  ok(await f.book(), 201);
  for (const [startDate, endDate] of [
    [START, END],
    ["2030-01-02T12:00:00Z", "2030-01-03T00:00:00Z"],
    ["2030-01-01T12:00:00Z", "2030-01-05T00:00:00Z"],
    ["2030-01-01T12:00:00Z", "2030-01-02T01:00:00Z"],
    ["2030-01-03T23:00:00Z", "2030-01-05T00:00:00Z"],
  ]) {
    denied(await f.book({ startDate, endDate }, "customer2"), 409);
  }
  ok(
    await f.book(
      { startDate: END, endDate: "2030-01-05T00:00:00Z" },
      "customer2",
    ),
    201,
  );
  const schedule = ok(await f.api.get("/api/cars/1/schedule"));
  assert.equal(schedule.length, 2);
  assert.ok(
    schedule.every(
      (x) =>
        !("CustomerId" in x) && !("CustomerName" in x) && !("OrderCode" in x),
    ),
    "Public schedule must not leak customer identity",
  );
});
test("SCHEDULE-02: concurrent customers cannot both book the same interval", async () => {
  const f = await fixture();
  const results = await Promise.all([
    f.book({}, "customer"),
    f.book({}, "customer2"),
  ]);
  assert.deepEqual(results.map((r) => r.status).sort(), [201, 409]);
  assert.equal(
    f.store.snapshot().RentalOrders.filter((o) => o.CarId === 1).length,
    1,
  );
});
test("SCHEDULE-03: maintenance blocks booking, and cancellation releases the interval", async () => {
  const f = await fixture();
  denied(await f.book({ carId: 7 }), 400, 409);
  const order = ok(await f.book(), 201);
  ok(
    await f.send("put", `/orders/${order.Id}/cancel`, {
      reason: "Đổi kế hoạch",
    }),
  );
  ok(await f.book({}, "customer2"), 201);
});
test("RBAC-01: customers cannot confirm, pickup, return, complete, alter cars or see audit/users", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  for (const action of ["confirm", "pickup", "return", "complete", "reject"])
    denied(await f.send("put", `/orders/${order.Id}/${action}`, {}), 403);
  denied(await f.send("put", "/cars/1/status", { status: "maintenance" }), 403);
  denied(await f.send("get", "/audit-logs"), 403);
  denied(await f.send("get", "/users"), 403);
  denied(await f.send("put", "/users/3", { role: "admin" }), 403);
});
test("STATE-01: invalid transitions and pickup before deposit/time are rejected", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/pickup`,
      {
        actualPickupDate: START,
        condition: "Tốt",
        odometerKm: 100,
        fuelLevel: "100%",
      },
      "employee",
    ),
    400,
    409,
  );
  ok(await f.send("put", `/orders/${order.Id}/confirm`, {}, "employee"));
  denied(
    await f.send("put", `/orders/${order.Id}/confirm`, {}, "employee"),
    400,
    409,
  );
  f.advance(START);
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/pickup`,
      {
        actualPickupDate: START,
        condition: "Tốt",
        odometerKm: 100,
        fuelLevel: "100%",
      },
      "employee",
    ),
    400,
    409,
  );
  denied(
    await f.send("put", `/orders/${order.Id}/complete`, {}, "employee"),
    400,
    409,
  );
});
test("CONTRACT-01: confirmation creates a printable contract scoped to its customer", async () => {
  const f = await fixture();
  const order = await f.confirmed();
  const contract = await f.send("get", `/orders/${order.Id}/contract`);
  assert.equal(contract.status, 200);
  assert.match(contract.headers["content-type"], /html/);
  assert.match(contract.text, /HỢP ĐỒNG|Hợp đồng|hợp đồng/);
  const storedContract = ok(
    await f.send("get", `/orders/${order.Id}`),
  ).contract;
  assert.ok(contract.text.includes(storedContract.ContractCode));
  denied(
    await f.send("get", `/orders/${order.Id}/contract`, undefined, "customer2"),
    403,
    404,
  );
});
test("PAY-01: simulated payment failure is recorded without credit; retry can succeed", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  const failed = await f.payment(order, { simulateFailure: true });
  assert.ok(
    [200, 201, 402].includes(failed.status),
    JSON.stringify(failed.body),
  );
  let payments = ok(await f.send("get", `/payments/order/${order.Id}`));
  assert.equal(payments.filter((p) => p.Status === "completed").length, 0);
  assert.equal(payments.filter((p) => p.Status === "failed").length, 1);
  assert.notEqual(
    ok(await f.send("get", `/orders/${order.Id}`)).PaymentStatus,
    "paid",
  );
  const paid = await f.payment(order);
  assert.ok([200, 201].includes(paid.status), JSON.stringify(paid.body));
  payments = ok(await f.send("get", `/payments/order/${order.Id}`));
  assert.equal(payments.filter((p) => p.Status === "completed").length, 1);
});
test("PAY-02: idempotency keys prevent duplicate charges and reject changed payloads", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  const body = { idempotencyKey: "same-attempt-0001" };
  const first = await f.payment(order, body);
  assert.ok([200, 201].includes(first.status), JSON.stringify(first.body));
  const replay = await f.payment(order, body);
  assert.ok([200, 201].includes(replay.status), JSON.stringify(replay.body));
  const rows = ok(await f.send("get", `/payments/order/${order.Id}`));
  assert.equal(rows.filter((p) => p.Status === "completed").length, 1);
  denied(
    await f.payment(order, {
      ...body,
      amount: Number(order.DepositAmount) + 1,
    }),
    400,
    409,
  );
});
test("PAY-03: negative amounts, overpayment and customer refunds are rejected", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  denied(await f.payment(order, { amount: -1 }), 400);
  denied(
    await f.payment(order, {
      amount: Number(order.TotalAmount) + 1,
      paymentType: "full_payment",
    }),
    400,
    409,
  );
  await f.payment(order);
  denied(await f.payment(order, { amount: 1, paymentType: "refund" }), 403);
});
test("CANCEL-01: pending cancellation is free; confirmed cancellation charges half deposit and bounds refund", async () => {
  const f = await fixture();
  const order = await f.confirmed();
  const paid = await f.payment(order);
  assert.ok([200, 201].includes(paid.status), JSON.stringify(paid.body));
  ok(
    await f.send("put", `/orders/${order.Id}/cancel`, {
      reason: "Khách thay đổi lịch trình",
    }),
  );
  const cancelled = ok(await f.send("get", `/orders/${order.Id}`));
  const fee = Math.round(Number(order.DepositAmount) * 0.5);
  assert.equal(cancelled.Status, "cancelled");
  assert.equal(Number(cancelled.CancellationFee), fee);
  assert.equal(Number(cancelled.TotalAmount), fee);
  denied(
    await f.payment(
      order,
      { paymentType: "refund", amount: Number(order.DepositAmount) },
      "employee",
    ),
    400,
    409,
  );
  const refund = await f.payment(
    order,
    { paymentType: "refund", amount: Number(order.DepositAmount) - fee },
    "employee",
  );
  assert.ok([200, 201].includes(refund.status), JSON.stringify(refund.body));
  denied(
    await f.payment(order, { paymentType: "refund", amount: 1 }, "employee"),
    400,
    409,
  );
  denied(
    await f.send("put", `/orders/${order.Id}/confirm`, {}, "employee"),
    400,
    409,
  );
});
test("RETURN-01: pickup records state; renting cannot be cancelled and unpaid orders cannot complete", async () => {
  const f = await fixture();
  const order = await f.renting();
  const picked = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(picked.Status, "renting");
  assert.ok(picked.ActualPickupDate);
  assert.ok(picked.handover);
  denied(
    await f.send("put", `/orders/${order.Id}/cancel`, {
      reason: "Đang sử dụng xe",
    }),
    400,
    409,
  );
  f.advance(END);
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: END,
        condition: "Nguyên vẹn",
        odometerKm: 10200,
        fuelLevel: "80%",
        extraFees: [],
      },
      "employee",
    ),
  );
  denied(
    await f.send("put", `/orders/${order.Id}/complete`, {}, "employee"),
    400,
    409,
  );
});
test("RETURN-02: return validates odometer, rejects future dates, and charges late days plus itemized fees", async () => {
  const f = await fixture();
  const order = await f.renting();
  f.advance("2030-01-04T01:00:00Z");
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-05T00:00:00Z",
        condition: "Tốt",
        odometerKm: 10500,
        fuelLevel: "60%",
        extraFees: [],
      },
      "employee",
    ),
    400,
    409,
  );
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-04T01:00:00Z",
        condition: "Tốt",
        odometerKm: 9999,
        fuelLevel: "60%",
        extraFees: [],
      },
      "employee",
    ),
    400,
    409,
  );
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-04T01:00:00Z",
        condition: "Tốt",
        odometerKm: 10500,
        fuelLevel: "60%",
        extraFees: [{ type: "damage", amount: -100, reason: "Không hợp lệ" }],
      },
      "employee",
    ),
    400,
    409,
  );
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-04T01:00:00Z",
        condition: "Trầy xước cửa trái",
        odometerKm: 10500,
        fuelLevel: "60%",
        needsMaintenance: true,
        extraFees: [
          { type: "damage", amount: 200000, reason: "Xước cửa theo biên bản" },
          { type: "fuel", amount: 100000, reason: "Bù nhiên liệu" },
        ],
      },
      "employee",
    ),
  );
  const returned = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(Number(returned.LateFee), Math.round(f.dailyRate * 1.5));
  assert.equal(
    Number(returned.TotalAmount),
    Number(order.BaseAmount) + Math.round(f.dailyRate * 1.5) + 300000,
  );
  assert.ok(returned.return);
  assert.ok(returned.extraFees.length >= 2);
  assert.equal(ok(await f.api.get("/api/cars/1")).Status, "maintenance");
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-04T01:00:00Z",
        condition: "Tốt",
        odometerKm: 10500,
        fuelLevel: "60%",
      },
      "employee",
    ),
    400,
    409,
  );
});
test("E2E-01: booking -> confirm -> deposit -> pickup -> return -> settle -> complete, with notifications/audit", async () => {
  const f = await fixture();
  const order = await f.renting();
  f.advance(END);
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: END,
        condition: "Nguyên vẹn",
        odometerKm: 10300,
        fuelLevel: "100%",
        extraFees: [],
      },
      "employee",
    ),
  );
  const balance = Number(order.TotalAmount) - Number(order.DepositAmount);
  const settlement = await f.payment(order, {
    paymentType: "full_payment",
    amount: balance,
  });
  assert.ok(
    [200, 201].includes(settlement.status),
    JSON.stringify(settlement.body),
  );
  ok(await f.send("put", `/orders/${order.Id}/complete`, {}, "employee"));
  const completed = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(completed.Status, "completed");
  assert.equal(completed.PaymentStatus, "paid");
  assert.equal(ok(await f.api.get("/api/cars/1")).Status, "available");
  const notifications = ok(await f.send("get", "/notifications"));
  assert.ok(notifications.length >= 5);
  const audit = ok(await f.send("get", "/audit-logs", undefined, "admin"));
  assert.ok(audit.length >= 6);
  assert.ok(audit.every((row) => row.UserId && row.Action));
  denied(
    await f.send("put", `/orders/${order.Id}/complete`, {}, "employee"),
    400,
    409,
  );
});
test("NOTIFY-01: reminders are deduplicated and read markers cannot alter another customer notification", async () => {
  const f = await fixture();
  const order = await f.confirmed();
  f.advance("2030-01-01T12:00:00Z");
  ok(await f.send("post", "/notifications/reminders", {}, "employee"));
  const first = ok(await f.send("get", "/notifications"));
  ok(await f.send("post", "/notifications/reminders", {}, "employee"));
  const second = ok(await f.send("get", "/notifications"));
  assert.equal(second.length, first.length);
  const notification = second[0];
  assert.ok(notification);
  denied(
    await f.send(
      "put",
      `/notifications/${notification.Id}/read`,
      {},
      "customer2",
    ),
    403,
    404,
  );
  ok(await f.send("put", `/notifications/${notification.Id}/read`, {}));
  const read = ok(await f.send("get", "/notifications")).find(
    (n) => n.Id === notification.Id,
  );
  assert.equal(Boolean(read.IsRead), true);
});
test("PAY-04: concurrent payment retries charge once; concurrent balances cannot overpay", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  const duplicate = await Promise.all([
    f.payment(order, { idempotencyKey: "concurrent-attempt-0001" }),
    f.payment(order, { idempotencyKey: "concurrent-attempt-0001" }),
  ]);
  assert.ok(
    duplicate.every((r) => [200, 201].includes(r.status)),
    JSON.stringify(duplicate.map((r) => r.body)),
  );
  let payments = ok(await f.send("get", `/payments/order/${order.Id}`));
  assert.equal(payments.filter((p) => p.Status === "completed").length, 1);
  const balance = Number(order.TotalAmount) - Number(order.DepositAmount);
  const simultaneous = await Promise.all([
    f.payment(order, { amount: balance, paymentType: "full_payment" }),
    f.payment(order, { amount: balance, paymentType: "full_payment" }),
  ]);
  assert.equal(
    simultaneous.filter((r) => [200, 201].includes(r.status)).length,
    1,
  );
  assert.equal(
    simultaneous.filter((r) => [400, 409].includes(r.status)).length,
    1,
  );
  payments = ok(await f.send("get", `/payments/order/${order.Id}`));
  assert.equal(
    payments
      .filter((p) => p.Status === "completed")
      .reduce((total, p) => total + Number(p.Amount), 0),
    Number(order.TotalAmount),
  );
});
test("CANCEL-02: pending cancellation is zero-cost and allows staff to refund the entire deposit", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  const deposit = await f.payment(order);
  assert.ok([200, 201].includes(deposit.status), JSON.stringify(deposit.body));
  ok(
    await f.send("put", `/orders/${order.Id}/cancel`, {
      reason: "Hủy trước xác nhận",
    }),
  );
  const cancelled = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(Number(cancelled.CancellationFee), 0);
  assert.equal(Number(cancelled.TotalAmount), 0);
  const refund = await f.payment(order, { paymentType: "refund" }, "employee");
  assert.ok([200, 201].includes(refund.status), JSON.stringify(refund.body));
  denied(
    await f.payment(order, { paymentType: "deposit", amount: 1000 }),
    400,
    409,
  );
});
test("CAR-01: active reservations prevent suspending a car; rejected order releases its slot", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  denied(
    await f.send("put", "/cars/1/status", { status: "suspended" }, "admin"),
    400,
    409,
  );
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/reject`,
      { reason: "Không đủ hồ sơ thuê xe" },
      "employee",
    ),
  );
  assert.equal(
    ok(await f.send("get", `/orders/${order.Id}`)).Status,
    "rejected",
  );
  ok(await f.book({}, "customer2"), 201);
});
test("PRICE-02: an odd VND daily rate produces an integer late fee and a payable final balance", async () => {
  const f = await fixture();
  const values = Object.fromEntries(
    [
      "Name",
      "Brand",
      "Model",
      "Year",
      "Seats",
      "Transmission",
      "FuelType",
      "DailyRate",
      "LicensePlate",
      "ImageUrl",
      "Description",
    ].map((key) => [key[0].toLowerCase() + key.slice(1), f.car[key]]),
  );
  ok(await f.send("put", "/cars/1", { ...values, dailyRate: 999001 }, "admin"));
  const order = await f.renting();
  f.advance("2030-01-04T01:00:00Z");
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: "2030-01-04T01:00:00Z",
        condition: "Nguyên vẹn",
        odometerKm: 10400,
        fuelLevel: "100%",
        extraFees: [],
      },
      "employee",
    ),
  );
  const returned = ok(await f.send("get", `/orders/${order.Id}`));
  assert.equal(Number(returned.LateFee), Math.round(999001 * 1.5));
  assert.ok(Number.isInteger(Number(returned.BalanceDue)));
  const settlement = await f.payment(order, {
    paymentType: "full_payment",
    amount: Number(returned.BalanceDue),
  });
  assert.ok(
    [200, 201].includes(settlement.status),
    JSON.stringify(settlement.body),
  );
  ok(await f.send("put", `/orders/${order.Id}/complete`, {}, "employee"));
});

test("AUTH-04 / UC02: username and case-insensitive email identify the same account", async () => {
  const f = await fixture();
  const byName = ok(
    await f.api
      .post("/api/auth/login")
      .send({ username: "customer", password: "Customer@123" }),
  );
  const byEmail = ok(
    await f.api
      .post("/api/auth/login")
      .send({ username: "CUSTOMER@RENTAL.EXAMPLE", password: "Customer@123" }),
  );
  assert.equal(byEmail.user.id, byName.user.id);
  assert.equal(byEmail.user.role, "customer");
  denied(
    await f.api
      .post("/api/auth/login")
      .send({ username: "customer@rental.example", password: "wrong" }),
    401,
  );
});
test("USER-01 / UC19: only admin creates employee accounts; unique identifiers and audit confidentiality are preserved", async () => {
  const f = await fixture();
  const values = {
    username: "newemployee",
    password: "EmployeeNew@123",
    fullName: "Nhân viên mới",
    email: "newemployee@example.com",
    phone: "0987654432",
    address: "TP. Hồ Chí Minh",
    role: "employee",
  };
  denied(await f.send("post", "/users", values, "customer"), 403);
  denied(await f.send("post", "/users", values, "employee"), 403);
  const created = ok(await f.send("post", "/users", values, "admin"), 201);
  assert.equal(created.role, "employee");
  assert.equal(created.email, values.email);
  assert.ok(!JSON.stringify(created).includes(values.password));
  assert.ok(!("PasswordHash" in created));
  const stored = f.store.snapshot().Users.find((u) => u.Id === created.id);
  assert.match(stored.PasswordHash, /^\$2[aby]\$/);
  assert.notEqual(stored.PasswordHash, values.password);
  const login = ok(
    await f.api
      .post("/api/auth/login")
      .send({ username: values.email, password: values.password }),
  );
  assert.equal(login.user.role, "employee");
  denied(
    await f.send(
      "post",
      "/users",
      { ...values, username: "differentstaff", phone: "0987654433" },
      "admin",
    ),
    409,
  );
  denied(
    await f.send(
      "post",
      "/users",
      {
        ...values,
        username: "differentstaff",
        email: "differentstaff@example.com",
      },
      "admin",
    ),
    409,
  );
  denied(
    await f.send(
      "post",
      "/users",
      {
        ...values,
        username: "badrole",
        email: "badrole@example.com",
        phone: "0987654434",
        role: "superuser",
      },
      "admin",
    ),
    400,
  );
  const users = ok(await f.send("get", "/users", undefined, "admin"));
  assert.ok(users.every((u) => !("PasswordHash" in u)));
  const audit = ok(await f.send("get", "/audit-logs", undefined, "admin"));
  const entry = audit.find(
    (row) => row.Action === "CREATE_USER" && row.EntityId === created.id,
  );
  assert.ok(entry);
  const serialized = JSON.stringify(entry);
  assert.ok(!serialized.includes(values.password));
  assert.ok(!serialized.includes(stored.PasswordHash));
  assert.ok(!serialized.includes("PasswordHash"));
});
test("USER-02 / UC19-20: role changes apply to existing tokens and the active admin cannot lock or demote itself", async () => {
  const f = await fixture();
  const order = ok(await f.book(), 201);
  ok(await f.send("put", "/users/2", { role: "customer" }, "admin"));
  denied(
    await f.send("put", `/orders/${order.Id}/confirm`, {}, "employee"),
    403,
  );
  ok(await f.send("put", "/users/2", { role: "employee" }, "admin"));
  ok(await f.send("put", `/orders/${order.Id}/confirm`, {}, "employee"));
  denied(await f.send("put", "/users/1", { role: "customer" }, "admin"), 409);
  denied(await f.send("put", "/users/1", { isActive: false }, "admin"), 409);
  assert.equal(
    ok(await f.send("get", "/auth/me", undefined, "admin")).role,
    "admin",
  );
});
test("CAR-02 / UC18: employee cannot create, edit or suspend vehicles; admin can save valid unique vehicles", async () => {
  const f = await fixture();
  const values = Object.fromEntries(
    [
      "Name",
      "Brand",
      "Model",
      "Year",
      "Seats",
      "Transmission",
      "FuelType",
      "DailyRate",
      "LicensePlate",
      "ImageUrl",
      "Description",
    ].map((key) => [key[0].toLowerCase() + key.slice(1), f.car[key]]),
  );
  const newCar = {
    ...values,
    name: "Toyota Vios kiểm thử",
    licensePlate: "51T-999.01",
  };
  denied(await f.send("post", "/cars", newCar, "employee"), 403);
  denied(await f.send("put", "/cars/1", values, "employee"), 403);
  denied(
    await f.send("put", "/cars/1/status", { status: "suspended" }, "employee"),
    403,
  );
  const created = ok(await f.send("post", "/cars", newCar, "admin"), 201);
  assert.equal(created.LicensePlate, newCar.licensePlate);
  assert.equal(created.Status, "available");
  denied(await f.send("post", "/cars", newCar, "admin"), 409);
  ok(
    await f.send(
      "put",
      `/cars/${created.Id}/status`,
      { status: "suspended" },
      "admin",
    ),
  );
  denied(await f.book({ carId: created.Id }), 409);
});
test("CONTRACT-02 / UC17: staff may edit confirmed contract terms before pickup; customer edits and post-pickup changes are blocked", async () => {
  const f = await fixture();
  const order = await f.confirmed();
  const original = ok(await f.send("get", `/orders/${order.Id}`)).contract;
  const terms =
    '<script>alert("xss")</script>\nGiao xe tại văn phòng & đối chiếu CCCD.';
  denied(
    await f.send("put", `/orders/${order.Id}/contract`, { terms }, "customer"),
    403,
  );
  denied(
    await f.send("put", `/orders/${order.Id}/contract`, { terms }, "customer2"),
    403,
  );
  const changed = ok(
    await f.send("put", `/orders/${order.Id}/contract`, { terms }, "employee"),
  );
  assert.equal(changed.RentalTerms, terms);
  assert.equal(changed.ContractCode, original.ContractCode);
  assert.equal(Number(changed.TotalAmount), Number(original.TotalAmount));
  assert.equal(Number(changed.DepositAmount), Number(original.DepositAmount));
  const html = await f.send("get", `/orders/${order.Id}/contract`);
  assert.equal(html.status, 200);
  assert.ok(html.text.includes("&lt;script&gt;"));
  assert.ok(!html.text.includes("<script>"));
  const terms2 = "Điều khoản thay thế hợp lệ";
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/contract`,
      { terms: terms2 },
      "admin",
    ),
  );
  const replacement = await f.send("get", `/orders/${order.Id}/contract`);
  assert.ok(replacement.text.includes(terms2));
  assert.ok(!replacement.text.includes("&lt;script&gt;"));
  assert.equal((replacement.text.match(/CUSTOM_TERMS_START/g) || []).length, 1);
  const paid = await f.payment(order);
  assert.ok([200, 201].includes(paid.status), JSON.stringify(paid.body));
  f.advance(START);
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/pickup`,
      {
        actualPickupDate: START,
        condition: "Nguyên vẹn",
        odometerKm: 10000,
        fuelLevel: "100%",
      },
      "employee",
    ),
  );
  denied(
    await f.send(
      "put",
      `/orders/${order.Id}/contract`,
      { terms: "Sửa sau khi nhận" },
      "employee",
    ),
    409,
  );
  assert.equal(
    ok(await f.send("get", `/orders/${order.Id}`)).contract.RentalTerms,
    terms2,
  );
  const audit = ok(await f.send("get", "/audit-logs", undefined, "admin"));
  assert.equal(
    audit.filter((row) => row.Action === "UPDATE_CONTRACT").length,
    2,
  );
});
test("REPORT-01 / UC22: report date windows count created orders and completed cashflow including refunds, excluding failures", async () => {
  const f = await fixture();
  const first = ok(await f.book(), 201);
  const firstPayment = await f.payment(first);
  assert.ok(
    [200, 201].includes(firstPayment.status),
    JSON.stringify(firstPayment.body),
  );
  f.advance("2030-01-10T12:00:00Z");
  const second = ok(
    await f.book({
      carId: 2,
      startDate: "2030-01-11T00:00:00Z",
      endDate: "2030-01-13T00:00:00Z",
    }),
    201,
  );
  await f.payment(second, { simulateFailure: true });
  const secondPayment = await f.payment(second);
  assert.ok(
    [200, 201].includes(secondPayment.status),
    JSON.stringify(secondPayment.body),
  );
  f.advance("2030-01-20T12:00:00Z");
  ok(
    await f.send("put", `/orders/${first.Id}/cancel`, {
      reason: "Hoàn tiền kiểm thử báo cáo",
    }),
  );
  const refund = await f.payment(first, { paymentType: "refund" }, "employee");
  assert.ok([200, 201].includes(refund.status), JSON.stringify(refund.body));
  const report = async (startDate, endDate) =>
    ok(
      await f.send(
        "get",
        `/reports?${new URLSearchParams({ startDate, endDate })}`,
        undefined,
        "admin",
      ),
    );
  const early = await report("2030-01-01T00:00:00Z", "2030-01-10T12:00:00Z");
  assert.equal(early.totalOrders, 1);
  assert.equal(Number(early.totalRevenue), Number(first.DepositAmount));
  const middle = await report("2030-01-10T12:00:00Z", "2030-01-20T12:00:00Z");
  assert.equal(middle.totalOrders, 1);
  assert.equal(Number(middle.totalRevenue), Number(second.DepositAmount));
  const late = await report("2030-01-20T12:00:00Z", "2030-01-21T00:00:00Z");
  assert.equal(late.totalOrders, 0);
  assert.equal(Number(late.totalRevenue), -Number(first.DepositAmount));
  const combined = await report("2030-01-01T00:00:00Z", "2030-01-21T00:00:00Z");
  assert.equal(combined.totalOrders, 2);
  assert.equal(Number(combined.totalRevenue), Number(second.DepositAmount));
  assert.equal(
    combined.revenueByMonth.reduce((sum, row) => sum + Number(row.revenue), 0),
    Number(second.DepositAmount),
  );
  assert.equal(
    combined.vehicleUtilization.reduce(
      (sum, row) => sum + Number(row.revenue),
      0,
    ),
    Number(second.DepositAmount),
  );
});
test("REPORT-02 / UC22: invalid/incomplete/reversed ranges are rejected and empty valid windows return zero aggregates", async () => {
  const f = await fixture();
  for (const query of [
    { startDate: START },
    { endDate: END },
    { startDate: END, endDate: START },
    { startDate: "invalid", endDate: END },
    { startDate: "2030-01-02T00:00", endDate: END },
    { startDate: "2028-01-01T00:00:00Z", endDate: END },
  ]) {
    denied(
      await f.send(
        "get",
        `/reports?${new URLSearchParams(query)}`,
        undefined,
        "admin",
      ),
      400,
    );
  }
  const empty = ok(
    await f.send(
      "get",
      `/reports?${new URLSearchParams({ startDate: START, endDate: END })}`,
      undefined,
      "admin",
    ),
  );
  assert.equal(empty.totalOrders, 0);
  assert.equal(Number(empty.totalRevenue), 0);
  assert.deepEqual(empty.revenueByMonth, []);
  denied(await f.send("get", "/reports"), 403);
});
test("REPORT-03 / UC22: vehicle utilization clips real rental times to the selected report interval", async () => {
  const f = await fixture();
  const order = await f.renting();
  f.advance(END);
  ok(
    await f.send(
      "put",
      `/orders/${order.Id}/return`,
      {
        actualReturnDate: END,
        condition: "Nguyên vẹn",
        odometerKm: 10400,
        fuelLevel: "100%",
        extraFees: [],
      },
      "employee",
    ),
  );
  const report = ok(
    await f.send(
      "get",
      `/reports?${new URLSearchParams({ startDate: "2030-01-02T12:00:00Z", endDate: "2030-01-03T12:00:00Z" })}`,
      undefined,
      "admin",
    ),
  );
  assert.equal(report.totalOrders, 0);
  assert.equal(Number(report.totalRevenue), 0);
  const row = report.vehicleUtilization.find((car) => car.carId === 1);
  assert.ok(row);
  assert.equal(row.rentedDays, 1);
  assert.equal(row.utilizationRate, 100);
  assert.ok(
    report.vehicleUtilization
      .filter((car) => car.carId !== 1)
      .every((car) => car.rentedDays === 0),
  );
});
