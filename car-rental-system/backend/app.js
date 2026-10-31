const express = require("express");
const fs = require("node:fs");
const path = require("node:path");
const cors = require("cors");
const helmet = require("helmet");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const { randomUUID, createHash } = require("node:crypto");
const R = require("./domain/rules");
const asyncRoute = (fn) => (req, res, next) =>
  Promise.resolve(fn(req, res, next)).catch(next);
function createApp({
  store,
  jwtSecret,
  clock = () => new Date(),
  corsOrigin = process.env.FRONTEND_ORIGIN || "http://localhost:5173",
} = {}) {
  if (!store || !jwtSecret || jwtSecret.length < 24)
    throw Error(
      "A store and JWT secret of at least 24 characters are required",
    );
  const app = express();
  app.disable("x-powered-by");
  app.use(
    helmet({
      contentSecurityPolicy: {
        directives: { imgSrc: ["'self'", "data:", "https:", "http:"] },
      },
    }),
  );
  app.use(cors({ origin: corsOrigin.split(",").map((s) => s.trim()) }));
  app.use(express.json({ limit: "100kb" }));
  const now = () => new Date(clock());
  const ok = (res, data, status = 200) =>
    res.status(status).json({ success: true, data });
  const auth = asyncRoute(async (req, res, next) => {
    const token = req.headers.authorization?.match(/^Bearer (.+)$/)?.[1];
    if (!token) R.fail(401, "Vui lòng đăng nhập");
    let payload;
    try {
      payload = jwt.verify(token, jwtSecret);
    } catch {
      R.fail(401, "Phiên đăng nhập không hợp lệ hoặc hết hạn");
    }
    const user = await store.get("Users", payload.id);
    if (!user || !user.IsActive)
      R.fail(401, "Tài khoản không tồn tại hoặc đã bị khóa");
    req.user = user;
    next();
  });
  const role =
    (...roles) =>
    (req, res, next) => {
      if (!roles.includes(req.user.Role))
        return res.status(403).json({
          success: false,
          message: "Bạn không có quyền thực hiện thao tác này",
        });
      next();
    };
  const staff = role("admin", "employee");
  const id = (v) => {
    const n = R.number(v, "Mã định danh", 1, 2147483647);
    if (!Number.isInteger(n)) R.fail(400, "Mã định danh không hợp lệ");
    return n;
  };
  async function getOrder(ctx, orderId, user) {
    const order = await ctx.get("RentalOrders", id(orderId));
    if (!order) R.fail(404, "Không tìm thấy đơn thuê");
    if (user.Role === "customer" && order.CustomerId !== user.Id)
      R.fail(403, "Bạn không có quyền xem đơn này");
    return order;
  }
  async function audit(
    ctx,
    user,
    action,
    entityType,
    entityId,
    oldValue,
    newValue,
    ip,
  ) {
    return ctx.insert("AuditLogs", {
      UserId: user.Id,
      Username: user.Username,
      Action: action,
      EntityType: entityType,
      EntityId: entityId,
      OldValue: oldValue ? JSON.stringify(oldValue) : null,
      NewValue: newValue ? JSON.stringify(newValue) : null,
      IpAddress: ip || null,
      CreatedAt: now(),
    });
  }
  async function notify(ctx, order, type, title, message) {
    return ctx.insert("Notifications", {
      UserId: order.CustomerId,
      OrderId: order.Id,
      Type: type,
      Title: title,
      Message: message,
      IsRead: false,
      CreatedAt: now(),
    });
  }
  async function refreshCar(ctx, carId, maintenance = false) {
    const car = await ctx.get("Cars", carId);
    const orders = (await ctx.list("RentalOrders")).filter(
      (o) => o.CarId === carId && R.active(o),
    );
    let status = maintenance
      ? "maintenance"
      : orders.some((o) => o.Status === "renting")
        ? "renting"
        : orders.length
          ? "booked"
          : ["maintenance", "suspended"].includes(car.Status)
            ? car.Status
            : "available";
    return ctx.update("Cars", carId, { Status: status, UpdatedAt: now() });
  }
  async function conflicts(ctx, carId, start, end, exclude) {
    return (await ctx.list("RentalOrders")).filter(
      (o) =>
        o.CarId === carId &&
        o.Id !== exclude &&
        R.active(o) &&
        R.overlaps(
          o.StartDate,
          o.Status === "renting" && new Date(o.EndDate) < now()
            ? new Date("9999-01-01")
            : o.EndDate,
          start,
          end,
        ),
    );
  }
  async function paymentState(ctx, order) {
    const net = R.paid(await ctx.list("Payments"), order.Id);
    return ctx.update("RentalOrders", order.Id, {
      PaymentStatus:
        net === 0
          ? "unpaid"
          : net >= Number(order.TotalAmount)
            ? "paid"
            : "partial",
      UpdatedAt: now(),
    });
  }
  async function detail(ctx, order) {
    const car = await ctx.get("Cars", order.CarId),
      customer = await ctx.get("Users", order.CustomerId),
      payments = (await ctx.list("Payments")).filter(
        (p) => p.OrderId === order.Id,
      );
    const totalPaid = R.paid(payments, order.Id);
    return {
      ...order,
      CarName: car.Name,
      CarImageUrl: car.ImageUrl,
      LicensePlate: car.LicensePlate,
      CustomerName: customer.FullName,
      CustomerPhone: customer.Phone,
      DailyRate: Number(order.BookedDailyRate),
      TotalPaid: totalPaid,
      PaidAmount: totalPaid,
      BalanceDue: Math.max(0, Number(order.TotalAmount) - totalPaid),
      RefundDue: Math.max(0, totalPaid - Number(order.TotalAmount)),
      payments,
      contract:
        (await ctx.list("Contracts")).find((c) => c.OrderId === order.Id) ||
        null,
      handover:
        (await ctx.list("VehicleHandovers")).find(
          (c) => c.OrderId === order.Id,
        ) || null,
      return:
        (await ctx.list("VehicleReturns")).find(
          (c) => c.OrderId === order.Id,
        ) || null,
      extraFees: (await ctx.list("ExtraFees")).filter(
        (c) => c.OrderId === order.Id,
      ),
    };
  }
  const mutation = (fn, status = 200) =>
    asyncRoute(async (req, res) =>
      ok(res, await store.transaction((ctx) => fn(ctx, req)), status),
    );
  const session = (u) => ({
    token: jwt.sign({ id: u.Id }, jwtSecret, {
      expiresIn: process.env.JWT_EXPIRES_IN || "12h",
    }),
    user: R.publicUser(u),
  });
  app.get(
    "/api/health",
    asyncRoute(async (req, res) => {
      await store.health();
      ok(res, {
        status: "ok",
        database: store.kind === "memory" ? "not-used" : "connected",
        storage: store.kind || "custom",
        mode: store.kind === "memory" ? "demo-or-test" : "sqlserver",
        paymentMode: "simulation",
      });
    }),
  );
  const attempts = new Map();
  app.post(
    "/api/auth/login",
    asyncRoute(async (req, res) => {
      const key = req.ip,
        previous = attempts.get(key) || { count: 0, at: Date.now() };
      if (Date.now() - previous.at > 600000) {
        previous.count = 0;
        previous.at = Date.now();
      }
      if (previous.count >= 30)
        R.fail(429, "Quá nhiều lần thử. Vui lòng thử lại sau 10 phút");
      previous.count++;
      attempts.set(key, previous);
      if (attempts.size > 10000) attempts.delete(attempts.keys().next().value);
      const username = R.text(
          req.body.username,
          "Tên đăng nhập hoặc email",
          100,
          true,
        ),
        password = R.text(req.body.password, "Mật khẩu", 128, true);
      const user = (await store.list("Users")).find(
        (u) =>
          u.Username.toLowerCase() === username.toLowerCase() ||
          u.Email.toLowerCase() === username.toLowerCase(),
      );
      if (
        !user ||
        !user.IsActive ||
        !(await bcrypt.compare(password, user.PasswordHash))
      )
        R.fail(401, "Tên đăng nhập hoặc mật khẩu không đúng");
      attempts.delete(key);
      ok(res, session(user));
    }),
  );
  function profile(body) {
    const fullName = R.text(body.fullName, "Họ tên", 100, true),
      email = R.text(body.email, "Email", 100, true).toLowerCase(),
      phone = R.text(body.phone, "Số điện thoại", 20);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      R.fail(400, "Email không hợp lệ");
    if (phone && !/^(\+84|0)[0-9]{9,10}$/.test(phone))
      R.fail(400, "Số điện thoại không hợp lệ");
    return {
      FullName: fullName,
      Email: email,
      Phone: phone || null,
      Address: R.text(body.address, "Địa chỉ", 255),
    };
  }
  app.post(
    "/api/auth/register",
    asyncRoute(async (req, res) => {
      const p = profile(req.body),
        username = R.text(req.body.username, "Tên đăng nhập", 50, true),
        password = R.text(req.body.password, "Mật khẩu", 128, true);
      if (!/^[A-Za-z0-9_]{3,50}$/.test(username))
        R.fail(400, "Tên đăng nhập từ 3–50 ký tự chữ, số hoặc gạch dưới");
      if (password.length < 8) R.fail(400, "Mật khẩu phải có ít nhất 8 ký tự");
      const hash = await bcrypt.hash(password, 12);
      const user = await store.transaction(async (ctx) => {
        if (
          (await ctx.list("Users")).some(
            (u) =>
              u.Username.toLowerCase() === username.toLowerCase() ||
              u.Email.toLowerCase() === p.Email ||
              (p.Phone && u.Phone === p.Phone),
          )
        )
          R.fail(409, "Tên đăng nhập, email hoặc số điện thoại đã tồn tại");
        const u = await ctx.insert("Users", {
          ...p,
          Username: username,
          PasswordHash: hash,
          Role: "customer",
          IsActive: true,
          CreatedAt: now(),
          UpdatedAt: now(),
        });
        await audit(
          ctx,
          u,
          "REGISTER",
          "User",
          u.Id,
          null,
          { Username: u.Username },
          req.ip,
        );
        return u;
      });
      ok(res, session(user), 201);
    }),
  );
  app.get("/api/auth/me", auth, (req, res) => ok(res, R.publicUser(req.user)));
  app.put(
    "/api/auth/profile",
    auth,
    mutation(async (ctx, req) => {
      const p = profile(req.body);
      if (
        (await ctx.list("Users")).some(
          (u) =>
            u.Id !== req.user.Id &&
            (u.Email.toLowerCase() === p.Email ||
              (p.Phone && u.Phone === p.Phone)),
        )
      )
        R.fail(409, "Email hoặc số điện thoại đã tồn tại");
      const updated = await ctx.update("Users", req.user.Id, {
        ...p,
        UpdatedAt: now(),
      });
      await audit(
        ctx,
        req.user,
        "UPDATE_PROFILE",
        "User",
        req.user.Id,
        null,
        p,
        req.ip,
      );
      return R.publicUser(updated);
    }),
  );
  app.get(
    "/api/cars",
    asyncRoute(async (req, res) => {
      let cars = await store.list("Cars");
      const q = String(req.query.search || "").toLowerCase();
      if (q)
        cars = cars.filter((c) =>
          [c.Name, c.Brand, c.LicensePlate].some((v) =>
            String(v).toLowerCase().includes(q),
          ),
        );
      if (req.query.status)
        cars = cars.filter((c) => c.Status === req.query.status);
      if (req.query.seats)
        cars = cars.filter((c) => c.Seats >= Number(req.query.seats));
      if (req.query.startDate || req.query.endDate) {
        const { start, end } = R.range(
          req.query.startDate,
          req.query.endDate,
          now(),
        );
        const orders = await store.list("RentalOrders");
        cars = cars.filter(
          (c) =>
            !["maintenance", "suspended"].includes(c.Status) &&
            !orders.some(
              (o) =>
                o.CarId === c.Id &&
                R.active(o) &&
                R.overlaps(
                  o.StartDate,
                  o.Status === "renting" && new Date(o.EndDate) < now()
                    ? new Date("9999-01-01")
                    : o.EndDate,
                  start,
                  end,
                ),
            ),
        );
      }
      ok(res, cars);
    }),
  );
  app.get(
    "/api/cars/:id/availability",
    asyncRoute(async (req, res) => {
      const car = await store.get("Cars", id(req.params.id));
      if (!car) R.fail(404, "Không tìm thấy xe");
      const { start, end } = R.range(
        req.query.startDate,
        req.query.endDate,
        now(),
      );
      const overlapping = await conflicts(store, car.Id, start, end);
      ok(res, {
        available:
          !["maintenance", "suspended"].includes(car.Status) &&
          !overlapping.length,
        conflicts: overlapping.map((o) => ({
          StartDate: o.StartDate,
          EndDate: o.EndDate,
          Status: o.Status,
        })),
      });
    }),
  );
  app.get(
    "/api/cars/:id/schedule",
    asyncRoute(async (req, res) => {
      const car = await store.get("Cars", id(req.params.id));
      if (!car) R.fail(404, "Không tìm thấy xe");
      ok(
        res,
        (await store.list("RentalOrders"))
          .filter((o) => o.CarId === car.Id && R.active(o))
          .map((o) => ({
            StartDate: o.StartDate,
            EndDate: o.EndDate,
            Status: o.Status,
          })),
      );
    }),
  );
  app.get(
    "/api/cars/:id",
    asyncRoute(async (req, res) => {
      const car = await store.get("Cars", id(req.params.id));
      if (!car) R.fail(404, "Không tìm thấy xe");
      ok(res, car);
    }),
  );
  function carValues(b) {
    const result = {
      Name: R.text(b.name, "Tên xe", 100, true),
      Brand: R.text(b.brand, "Hãng xe", 50, true),
      Model: R.text(b.model, "Dòng xe", 50),
      Year: R.number(b.year, "Năm sản xuất", 1990, now().getUTCFullYear() + 1),
      Seats: R.number(b.seats, "Số chỗ", 2, 50),
      Transmission: R.text(b.transmission, "Hộp số", 20, true),
      FuelType: R.text(b.fuelType, "Nhiên liệu", 20, true),
      DailyRate: R.number(b.dailyRate, "Giá thuê", 1000, 100000000),
      LicensePlate: R.text(b.licensePlate, "Biển số", 20, true).toUpperCase(),
      ImageUrl: R.text(b.imageUrl, "Đường dẫn ảnh", 500),
      Description: R.text(b.description, "Mô tả", 4000),
      DepositRate: 30,
    };
    if (!Number.isInteger(result.DailyRate))
      R.fail(400, "Giá thuê phải là số nguyên VND");
    if (!Number.isInteger(result.Seats) || !Number.isInteger(result.Year))
      R.fail(400, "Số chỗ và năm phải là số nguyên");
    if (result.ImageUrl && !/^(https?:\/\/|\/)/.test(result.ImageUrl))
      R.fail(
        400,
        "Ảnh phải là URL HTTP/HTTPS hoặc đường dẫn tương đối bắt đầu bằng /",
      );
    return result;
  }
  app.post(
    "/api/cars",
    auth,
    role("admin"),
    mutation(async (ctx, req) => {
      const values = carValues(req.body);
      if (
        (await ctx.list("Cars")).some(
          (c) => c.LicensePlate === values.LicensePlate,
        )
      )
        R.fail(409, "Biển số xe đã tồn tại");
      const car = await ctx.insert("Cars", {
        ...values,
        Status: "available",
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      await audit(
        ctx,
        req.user,
        "CREATE_CAR",
        "Car",
        car.Id,
        null,
        car,
        req.ip,
      );
      return car;
    }, 201),
  );
  app.put(
    "/api/cars/:id/status",
    auth,
    role("admin"),
    mutation(async (ctx, req) => {
      const car = await ctx.get("Cars", id(req.params.id));
      if (!car) R.fail(404, "Không tìm thấy xe");
      const status = req.body.status;
      if (!["available", "maintenance", "suspended"].includes(status))
        R.fail(400, "Chỉ đổi thủ công sang trống, bảo trì hoặc tạm ngưng");
      if (
        (await ctx.list("RentalOrders")).some(
          (o) => o.CarId === car.Id && R.active(o),
        )
      )
        R.fail(409, "Xe còn đơn hiệu lực; không thể đổi trạng thái thủ công");
      const updated = await ctx.update("Cars", car.Id, {
        Status: status,
        UpdatedAt: now(),
      });
      await audit(
        ctx,
        req.user,
        "CAR_STATUS",
        "Car",
        car.Id,
        car,
        updated,
        req.ip,
      );
      return updated;
    }),
  );
  app.put(
    "/api/cars/:id",
    auth,
    role("admin"),
    mutation(async (ctx, req) => {
      const car = await ctx.get("Cars", id(req.params.id));
      if (!car) R.fail(404, "Không tìm thấy xe");
      const values = carValues(req.body);
      if (
        (await ctx.list("Cars")).some(
          (c) => c.Id !== car.Id && c.LicensePlate === values.LicensePlate,
        )
      )
        R.fail(409, "Biển số xe đã tồn tại");
      const updated = await ctx.update("Cars", car.Id, {
        ...values,
        UpdatedAt: now(),
      });
      await audit(
        ctx,
        req.user,
        "UPDATE_CAR",
        "Car",
        car.Id,
        car,
        updated,
        req.ip,
      );
      return updated;
    }),
  );
  app.post(
    "/api/orders/quote",
    asyncRoute(async (req, res) => {
      const car = await store.get("Cars", id(req.body.carId));
      if (!car) R.fail(404, "Không tìm thấy xe");
      const { start, end } = R.range(
        req.body.startDate,
        req.body.endDate,
        now(),
      );
      ok(res, R.quote(car, start, end));
    }),
  );
  app.post(
    "/api/orders",
    auth,
    mutation(async (ctx, req) => {
      const car = await ctx.get("Cars", id(req.body.carId));
      if (!car) R.fail(404, "Không tìm thấy xe");
      const { start, end } = R.range(
        req.body.startDate,
        req.body.endDate,
        now(),
      );
      if (["maintenance", "suspended"].includes(car.Status))
        R.fail(409, "Xe đang bảo trì hoặc tạm ngưng");
      if ((await conflicts(ctx, car.Id, start, end)).length)
        R.fail(409, "Xe đã có lịch thuê trùng khoảng thời gian này");
      const q = R.quote(car, start, end);
      const order = await ctx.insert("RentalOrders", {
        OrderCode: `DX-${randomUUID().slice(0, 12).toUpperCase()}`,
        CustomerId: req.user.Id,
        CarId: car.Id,
        StartDate: start,
        EndDate: end,
        BookedDailyRate: q.dailyRate,
        DepositAmount: q.depositAmount,
        BaseAmount: q.baseAmount,
        TotalAmount: q.totalAmount,
        TotalExtraFee: 0,
        LateFee: 0,
        EarlyReturnFee: 0,
        CancellationFee: 0,
        Status: "pending",
        PaymentStatus: "unpaid",
        Notes: R.text(req.body.notes, "Ghi chú", 4000),
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      await refreshCar(ctx, car.Id);
      await notify(
        ctx,
        order,
        "order_created",
        "Đặt xe thành công",
        `Đơn ${order.OrderCode} đang chờ xác nhận.`,
      );
      await audit(
        ctx,
        req.user,
        "CREATE_ORDER",
        "RentalOrder",
        order.Id,
        null,
        order,
        req.ip,
      );
      return detail(ctx, order);
    }, 201),
  );
  app.get(
    "/api/orders",
    auth,
    asyncRoute(async (req, res) => {
      let orders = (await store.list("RentalOrders")).filter(
        (o) => req.user.Role !== "customer" || o.CustomerId === req.user.Id,
      );
      if (req.query.status)
        orders = orders.filter((o) => o.Status === req.query.status);
      orders.sort((a, b) => b.Id - a.Id);
      ok(res, await Promise.all(orders.map((o) => detail(store, o))));
    }),
  );
  app.get(
    "/api/orders/:id/contract",
    auth,
    asyncRoute(async (req, res) => {
      const order = await getOrder(store, req.params.id, req.user),
        contract = (await store.list("Contracts")).find(
          (c) => c.OrderId === order.Id,
        );
      if (!contract) R.fail(404, "Hợp đồng được tạo khi xác nhận đơn");
      res.type("html").send(contract.Content);
    }),
  );
  app.put(
    "/api/orders/:id/contract",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.params.id, req.user);
      if (order.Status !== "confirmed" || order.ActualPickupDate)
        R.fail(
          409,
          "Chỉ sửa điều khoản hợp đồng sau xác nhận và trước khi giao xe",
        );
      const contract = (await ctx.list("Contracts")).find(
        (c) => c.OrderId === order.Id,
      );
      if (!contract) R.fail(404, "Không tìm thấy hợp đồng");
      const terms = R.text(req.body.terms, "Điều khoản", 10000, true);
      const section = `<!--CUSTOM_TERMS_START--><h2>Điều khoản bổ sung đã thỏa thuận</h2><p>${R.escape(terms).replace(/\n/g, "<br>")}</p><!--CUSTOM_TERMS_END-->`;
      const oldContent =
        contract.Content ||
        '<!doctype html><html lang="vi"><meta charset="utf-8"><body><h1>Hợp đồng thuê xe</h1></body></html>';
      const content = oldContent.includes("<!--CUSTOM_TERMS_START-->")
        ? oldContent.replace(
            /<!--CUSTOM_TERMS_START-->[\s\S]*?<!--CUSTOM_TERMS_END-->/,
            () => section,
          )
        : oldContent.replace("</body>", () => section + "</body>");
      const updated = await ctx.update("Contracts", contract.Id, {
        RentalTerms: terms,
        Content: content,
        UpdatedAt: now(),
      });
      await audit(
        ctx,
        req.user,
        "UPDATE_CONTRACT",
        "Contract",
        contract.Id,
        { RentalTerms: contract.RentalTerms },
        { RentalTerms: terms },
        req.ip,
      );
      await notify(
        ctx,
        order,
        "contract_updated",
        "Điều khoản hợp đồng đã cập nhật",
        `Đơn ${order.OrderCode}: nhân viên đã cập nhật điều khoản bổ sung. Vui lòng xem trước khi nhận xe.`,
      );
      return updated;
    }),
  );
  app.get(
    "/api/orders/:id",
    auth,
    asyncRoute(async (req, res) =>
      ok(
        res,
        await detail(store, await getOrder(store, req.params.id, req.user)),
      ),
    ),
  );
  app.put(
    "/api/orders/:id/confirm",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.params.id, req.user);
      if (order.Status !== "pending") R.fail(409, "Chỉ xác nhận đơn đang chờ");
      const car = await ctx.get("Cars", order.CarId);
      if (["maintenance", "suspended"].includes(car.Status))
        R.fail(409, "Xe không sẵn sàng");
      if (
        (await conflicts(ctx, car.Id, order.StartDate, order.EndDate, order.Id))
          .length
      )
        R.fail(409, "Đơn thuê bị trùng lịch");
      const customer = await ctx.get("Users", order.CustomerId),
        code = `HD-${order.OrderCode.slice(3)}`;
      const content = `<!doctype html><html lang="vi"><head><meta charset="UTF-8"><title>${R.escape(code)}</title><style>body{font:16px Arial;max-width:800px;margin:40px auto;line-height:1.7;padding:20px}h1{text-align:center}table{width:100%;border-collapse:collapse}td{padding:8px;border:1px solid #ccc}@media print{button{display:none}}</style></head><body><h1>HỢP ĐỒNG THUÊ XE DU LỊCH</h1><p>Mã: ${R.escape(code)} • Ngày tạo: ${R.escape(now().toISOString())}</p><p>Khách hàng: ${R.escape(customer.FullName)} • ${R.escape(customer.Phone)}</p><p>Xe: ${R.escape(car.Name)} • Biển số: ${R.escape(car.LicensePlate)}</p><table><tr><td>Thời gian (UTC)</td><td>${R.escape(new Date(order.StartDate).toISOString())} – ${R.escape(new Date(order.EndDate).toISOString())}</td></tr><tr><td>Giá/ngày</td><td>${Number(order.BookedDailyRate).toLocaleString("vi-VN")} ₫</td></tr><tr><td>Tiền thuê</td><td>${Number(order.BaseAmount).toLocaleString("vi-VN")} ₫</td></tr><tr><td>Đặt cọc (khấu trừ tiền thuê)</td><td>${Number(order.DepositAmount).toLocaleString("vi-VN")} ₫</td></tr></table><p>Quy ước: làm tròn lên mỗi 24 giờ, tối thiểu một ngày. Tiền cọc theo số tiền ghi ở trên, được khấu trừ vào tiền thuê. Trả trễ: mỗi ngày bắt đầu trễ thu 150% đơn giá đã đặt. Trả sớm không hoàn tiền ngày chưa dùng và không phụ thu. Hủy sau xác nhận: phí bằng 50% tiền cọc. Không hủy khi đang thuê. Phí hư hỏng, nhiên liệu, vệ sinh được ghi rõ trong biên bản trả xe.</p><p>Thanh toán trong hệ thống là mô phỏng, không chuyển tiền thật. Hợp đồng điện tử phục vụ đồ án; xác nhận đơn tạo bản chụp điều khoản tại thời điểm thuê.</p><p>Khách hàng ___________________ &nbsp; Đại diện bên cho thuê ___________________</p></body></html>`;
      await ctx.insert("Contracts", {
        OrderId: order.Id,
        ContractCode: code,
        ContractNumber: code,
        CustomerName: customer.FullName,
        CustomerPhone: customer.Phone,
        CustomerEmail: customer.Email,
        CarInfo: `${car.Name} - ${car.LicensePlate}`,
        TotalAmount: Number(order.TotalAmount),
        DepositAmount: Number(order.DepositAmount),
        RentalTerms: "Bản điều khoản tại thời điểm xác nhận; xem Content.",
        Content: content,
        Status: "active",
        SignedAt: now(),
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      const updated = await ctx.update("RentalOrders", order.Id, {
        Status: "confirmed",
        ConfirmedByUserId: req.user.Id,
        ConfirmedAt: now(),
        UpdatedAt: now(),
      });
      await notify(
        ctx,
        order,
        "order_confirmed",
        "Đơn thuê đã xác nhận",
        `Đơn ${order.OrderCode} đã xác nhận. Hợp đồng đã được tạo. Thanh toán cọc trước khi nhận xe.`,
      );
      await audit(
        ctx,
        req.user,
        "CONFIRM_ORDER",
        "RentalOrder",
        order.Id,
        order,
        updated,
        req.ip,
      );
      return detail(ctx, updated);
    }),
  );
  app.put(
    "/api/orders/:id/pickup",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.params.id, req.user);
      if (order.Status !== "confirmed")
        R.fail(409, "Chỉ giao xe cho đơn đã xác nhận");
      const at = R.date(req.body.actualPickupDate, "Thời điểm nhận xe");
      if (
        at < new Date(order.StartDate) ||
        at > new Date(now().getTime() + 300000) ||
        at >= new Date(order.EndDate)
      )
        R.fail(
          400,
          "Thời điểm nhận phải trong thời gian thuê và không ở tương lai",
        );
      if (
        R.paid(await ctx.list("Payments"), order.Id) <
        Number(order.DepositAmount)
      )
        R.fail(409, "Cần thanh toán đủ tiền cọc trước khi nhận xe");
      const car = await ctx.get("Cars", order.CarId);
      if (
        ["maintenance", "suspended"].includes(car.Status) ||
        (await ctx.list("RentalOrders")).some(
          (o) =>
            o.Id !== order.Id &&
            o.CarId === order.CarId &&
            o.Status === "renting" &&
            !o.ActualReturnDate,
        )
      )
        R.fail(409, "Xe chưa sẵn sàng giao");
      const condition = R.text(req.body.condition, "Tình trạng xe", 4000, true);
      await ctx.insert("VehicleHandovers", {
        OrderId: order.Id,
        EmployeeId: req.user.Id,
        HandoverAt: at,
        OdometerKm: R.number(req.body.odometerKm, "Số km", 0, 10000000),
        FuelLevel: R.text(
          String(req.body.fuelLevel ?? ""),
          "Mức nhiên liệu",
          50,
          true,
        ),
        VehicleCondition: condition,
        Notes: R.text(req.body.notes, "Ghi chú", 4000),
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      const updated = await ctx.update("RentalOrders", order.Id, {
        Status: "renting",
        ActualPickupDate: at,
        PickupCondition: condition,
        UpdatedAt: now(),
      });
      await refreshCar(ctx, order.CarId);
      await notify(
        ctx,
        order,
        "car_picked_up",
        "Đã bàn giao xe",
        `Đơn ${order.OrderCode} bắt đầu thuê. Vui lòng trả đúng giờ.`,
      );
      await audit(
        ctx,
        req.user,
        "PICKUP_CAR",
        "RentalOrder",
        order.Id,
        order,
        updated,
        req.ip,
      );
      return detail(ctx, updated);
    }),
  );
  app.put(
    "/api/orders/:id/return",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.params.id, req.user);
      if (order.Status !== "renting" || order.ActualReturnDate)
        R.fail(409, "Đơn không ở trạng thái đang thuê hoặc đã trả xe");
      const at = R.date(req.body.actualReturnDate, "Thời điểm trả xe");
      if (
        at < new Date(order.ActualPickupDate) ||
        at > new Date(now().getTime() + 300000)
      )
        R.fail(400, "Thời điểm trả phải sau khi nhận xe và không ở tương lai");
      const handover = (await ctx.list("VehicleHandovers")).find(
          (h) => h.OrderId === order.Id,
        ),
        odometer = R.number(req.body.odometerKm, "Số km", 0, 10000000);
      if (odometer < Number(handover.OdometerKm))
        R.fail(400, "Số km trả không được nhỏ hơn lúc nhận");
      const condition = R.text(req.body.condition, "Tình trạng xe", 4000, true);
      if (
        req.body.needsMaintenance != null &&
        typeof req.body.needsMaintenance !== "boolean"
      )
        R.fail(400, "Cờ bảo trì không hợp lệ");
      const returned = await ctx.insert("VehicleReturns", {
        OrderId: order.Id,
        EmployeeId: req.user.Id,
        ReturnedAt: at,
        OdometerKm: odometer,
        FuelLevel: R.text(
          String(req.body.fuelLevel ?? ""),
          "Mức nhiên liệu",
          50,
          true,
        ),
        VehicleCondition: condition,
        NeedsMaintenance: !!req.body.needsMaintenance,
        Notes: R.text(req.body.notes, "Ghi chú", 4000),
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      const lateFee = Math.round(
        Math.max(0, Math.ceil((at - new Date(order.EndDate)) / R.DAY)) *
          Number(order.BookedDailyRate) *
          1.5,
      );
      const extra = req.body.extraFees ?? [];
      if (!Array.isArray(extra) || extra.length > 20)
        R.fail(400, "Danh sách phí phát sinh không hợp lệ");
      let totalExtra = lateFee;
      if (lateFee)
        await ctx.insert("ExtraFees", {
          OrderId: order.Id,
          ReturnId: returned.Id,
          FeeType: "late",
          Amount: lateFee,
          Reason: "Trả trễ: 150% đơn giá/ngày bắt đầu trễ",
          CreatedByUserId: req.user.Id,
          CreatedAt: now(),
          UpdatedAt: now(),
        });
      for (const fee of extra) {
        if (!["damage", "fuel", "cleaning", "other"].includes(fee.type))
          R.fail(400, "Loại phụ phí không hợp lệ");
        const amount = R.number(fee.amount, "Phụ phí", 1, 100000000);
        if (!Number.isInteger(amount))
          R.fail(400, "Phụ phí phải là số nguyên VND");
        totalExtra += amount;
        await ctx.insert("ExtraFees", {
          OrderId: order.Id,
          ReturnId: returned.Id,
          FeeType: fee.type,
          Amount: amount,
          Reason: R.text(fee.reason, "Lý do phụ phí", 1000, true),
          CreatedByUserId: req.user.Id,
          CreatedAt: now(),
          UpdatedAt: now(),
        });
      }
      let updated = await ctx.update("RentalOrders", order.Id, {
        ActualReturnDate: at,
        ReturnCondition: condition,
        LateFee: lateFee,
        TotalExtraFee: totalExtra,
        TotalAmount: Number(order.BaseAmount) + totalExtra,
        UpdatedAt: now(),
      });
      updated = await paymentState(ctx, updated);
      await refreshCar(ctx, order.CarId, !!req.body.needsMaintenance);
      await notify(
        ctx,
        order,
        "car_returned",
        "Đã nhận trả xe",
        `Đơn ${order.OrderCode} đã trả xe. Phụ phí ${totalExtra.toLocaleString("vi-VN")} ₫. Vui lòng quyết toán để hoàn tất.`,
      );
      await audit(
        ctx,
        req.user,
        "RETURN_CAR",
        "RentalOrder",
        order.Id,
        order,
        updated,
        req.ip,
      );
      return detail(ctx, updated);
    }),
  );
  app.put(
    "/api/orders/:id/complete",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.params.id, req.user);
      if (order.Status !== "renting" || !order.ActualReturnDate)
        R.fail(409, "Cần ghi nhận trả xe trước khi hoàn tất");
      if (
        R.paid(await ctx.list("Payments"), order.Id) < Number(order.TotalAmount)
      )
        R.fail(409, "Chưa thanh toán đủ để hoàn tất đơn");
      const updated = await ctx.update("RentalOrders", order.Id, {
        Status: "completed",
        PaymentStatus: "paid",
        UpdatedAt: now(),
      });
      const contract = (await ctx.list("Contracts")).find(
        (c) => c.OrderId === order.Id,
      );
      if (contract)
        await ctx.update("Contracts", contract.Id, {
          Status: "completed",
          UpdatedAt: now(),
        });
      await refreshCar(ctx, order.CarId);
      await notify(
        ctx,
        order,
        "order_completed",
        "Đơn thuê đã hoàn tất",
        `Cảm ơn bạn đã sử dụng dịch vụ. Đơn ${order.OrderCode} đã quyết toán.`,
      );
      await audit(
        ctx,
        req.user,
        "COMPLETE_ORDER",
        "RentalOrder",
        order.Id,
        order,
        updated,
        req.ip,
      );
      return detail(ctx, updated);
    }),
  );
  for (const action of ["cancel", "reject"])
    app.put(
      `/api/orders/:id/${action}`,
      auth,
      ...(action === "reject" ? [staff] : []),
      mutation(async (ctx, req) => {
        const order = await getOrder(ctx, req.params.id, req.user);
        if (
          !["pending", "confirmed"].includes(order.Status) ||
          (action === "reject" && order.Status !== "pending")
        )
          R.fail(409, "Trạng thái đơn không cho phép hủy/từ chối");
        const reason = R.text(req.body.reason, "Lý do", 1000, true);
        const fee =
          action === "cancel" && order.Status === "confirmed"
            ? Math.round(Number(order.DepositAmount) * 0.5)
            : 0;
        let updated = await ctx.update("RentalOrders", order.Id, {
          Status: action === "reject" ? "rejected" : "cancelled",
          CancellationFee: fee,
          TotalAmount: fee,
          CancellationReason: reason,
          ...(action === "reject"
            ? {
                RejectedByUserId: req.user.Id,
                RejectedAt: now(),
                RejectionReason: reason,
              }
            : {}),
          UpdatedAt: now(),
        });
        updated = await paymentState(ctx, updated);
        const contract = (await ctx.list("Contracts")).find(
          (c) => c.OrderId === order.Id,
        );
        if (contract)
          await ctx.update("Contracts", contract.Id, {
            Status: "cancelled",
            UpdatedAt: now(),
          });
        await refreshCar(ctx, order.CarId);
        await notify(
          ctx,
          order,
          "order_cancelled",
          action === "reject" ? "Đơn bị từ chối" : "Đơn thuê đã hủy",
          `Đơn ${order.OrderCode}: ${reason}. Phí hủy ${fee.toLocaleString("vi-VN")} ₫. Khoản thừa được nhân viên hoàn qua thanh toán mô phỏng.`,
        );
        await audit(
          ctx,
          req.user,
          action === "reject" ? "REJECT_ORDER" : "CANCEL_ORDER",
          "RentalOrder",
          order.Id,
          order,
          updated,
          req.ip,
        );
        return detail(ctx, updated);
      }),
    );
  app.get(
    "/api/payments/order/:orderId",
    auth,
    asyncRoute(async (req, res) => {
      const order = await getOrder(store, req.params.orderId, req.user);
      ok(
        res,
        (await store.list("Payments")).filter((p) => p.OrderId === order.Id),
      );
    }),
  );
  app.post(
    "/api/payments",
    auth,
    mutation(async (ctx, req) => {
      const order = await getOrder(ctx, req.body.orderId, req.user),
        type = req.body.paymentType,
        amount = R.number(req.body.amount, "Số tiền", 1, 1e12),
        key = R.text(req.body.idempotencyKey, "Mã chống lặp", 100, true);
      if (
        !["deposit", "full_payment", "refund"].includes(type) ||
        req.body.method !== "simulation"
      )
        R.fail(
          400,
          "Chỉ hỗ trợ thanh toán mô phỏng: cọc, còn lại hoặc hoàn tiền",
        );
      if (!Number.isInteger(amount))
        R.fail(400, "Số tiền phải là số nguyên VND");
      if (
        req.body.simulateFailure != null &&
        typeof req.body.simulateFailure !== "boolean"
      )
        R.fail(400, "Trạng thái mô phỏng không hợp lệ");
      const fingerprint = createHash("sha256")
          .update(
            JSON.stringify({
              orderId: order.Id,
              type,
              amount,
              fail: !!req.body.simulateFailure,
            }),
          )
          .digest("hex"),
        payments = await ctx.list("Payments");
      const prior = payments.find((p) => p.IdempotencyKey === key);
      if (prior) {
        if (
          prior.CreatedByUserId !== req.user.Id ||
          prior.RequestFingerprint !== fingerprint
        )
          R.fail(409, "Mã giao dịch đã dùng cho yêu cầu khác");
        return prior;
      }
      const net = R.paid(payments, order.Id);
      if (type === "refund") {
        if (req.user.Role === "customer")
          R.fail(403, "Chỉ nhân viên hoặc quản trị viên được hoàn tiền");
        if (amount > Math.max(0, net - Number(order.TotalAmount)))
          R.fail(409, "Số tiền hoàn vượt khoản thanh toán thừa");
      } else {
        if (
          ["completed", "rejected"].includes(order.Status) ||
          (order.Status === "cancelled" && type === "deposit")
        )
          R.fail(409, "Không thể thanh toán cho đơn ở trạng thái này");
        if (
          type === "deposit" &&
          !["pending", "confirmed"].includes(order.Status)
        )
          R.fail(409, "Chỉ đặt cọc trước khi nhận xe");
        const due =
          type === "deposit"
            ? Number(order.DepositAmount) - net
            : Number(order.TotalAmount) - net;
        if (amount > due) R.fail(409, "Số tiền vượt khoản cần thanh toán");
      }
      const payment = await ctx.insert("Payments", {
        OrderId: order.Id,
        Amount: amount,
        PaymentType: type,
        PaymentMethod: "simulation",
        Status: req.body.simulateFailure ? "failed" : "completed",
        TransactionCode: `SIM-${randomUUID()}`,
        TransactionRef: `SIM-${randomUUID()}`,
        IdempotencyKey: key,
        RequestFingerprint: fingerprint,
        CreatedByUserId: req.user.Id,
        Notes: "Thanh toán mô phỏng — không chuyển tiền thật",
        CreatedAt: now(),
        UpdatedAt: now(),
      });
      if (payment.Status === "completed") await paymentState(ctx, order);
      await notify(
        ctx,
        order,
        payment.Status === "failed"
          ? "payment_failed"
          : type === "refund"
            ? "payment_refunded"
            : "payment_received",
        payment.Status === "failed"
          ? "Thanh toán mô phỏng thất bại"
          : type === "refund"
            ? "Hoàn tiền mô phỏng thành công"
            : "Thanh toán mô phỏng thành công",
        `Đơn ${order.OrderCode}: ${amount.toLocaleString("vi-VN")} ₫ (${payment.TransactionCode}). Không chuyển tiền thật.`,
      );
      await audit(
        ctx,
        req.user,
        "PAYMENT_" + payment.Status.toUpperCase(),
        "Payment",
        payment.Id,
        null,
        payment,
        req.ip,
      );
      return payment;
    }),
  );
  app.get(
    "/api/notifications",
    auth,
    asyncRoute(async (req, res) =>
      ok(
        res,
        (await store.list("Notifications"))
          .filter((n) => n.UserId === req.user.Id)
          .sort((a, b) => b.Id - a.Id),
      ),
    ),
  );
  app.put(
    "/api/notifications/read-all",
    auth,
    mutation(async (ctx, req) => {
      const rows = (await ctx.list("Notifications")).filter(
        (n) => n.UserId === req.user.Id && !n.IsRead,
      );
      for (const n of rows)
        await ctx.update("Notifications", n.Id, { IsRead: true });
      return { updated: rows.length };
    }),
  );
  app.put(
    "/api/notifications/:id/read",
    auth,
    mutation(async (ctx, req) => {
      const n = await ctx.get("Notifications", id(req.params.id));
      if (!n || n.UserId !== req.user.Id)
        R.fail(404, "Không tìm thấy thông báo");
      return ctx.update("Notifications", n.Id, { IsRead: true });
    }),
  );
  app.post(
    "/api/notifications/reminders",
    auth,
    staff,
    mutation(async (ctx, req) => {
      const notifications = await ctx.list("Notifications"),
        orders = (await ctx.list("RentalOrders")).filter(
          (o) =>
            o.Status === "confirmed" &&
            new Date(o.StartDate) >= now() &&
            new Date(o.StartDate) - now() <= R.DAY,
        );
      let count = 0;
      for (const order of orders) {
        if (
          notifications.some(
            (n) => n.OrderId === order.Id && n.Type === "pickup_reminder",
          )
        )
          continue;
        await notify(
          ctx,
          order,
          "pickup_reminder",
          "Sắp đến giờ nhận xe",
          `Đơn ${order.OrderCode} nhận xe lúc ${new Date(order.StartDate).toISOString()}. Vui lòng mang CCCD/GPLX và thanh toán đủ cọc.`,
        );
        count++;
      }
      await audit(
        ctx,
        req.user,
        "SEND_REMINDERS",
        "Notification",
        null,
        null,
        { sent: count },
        req.ip,
      );
      return { sent: count };
    }),
  );
  app.get(
    "/api/audit-logs",
    auth,
    role("admin"),
    asyncRoute(async (req, res) =>
      ok(
        res,
        (await store.list("AuditLogs"))
          .sort((a, b) => b.Id - a.Id)
          .slice(0, 1000),
      ),
    ),
  );
  app.get(
    "/api/users",
    auth,
    role("admin"),
    asyncRoute(async (req, res) =>
      ok(
        res,
        (await store.list("Users")).map(({ PasswordHash, ...u }) => u),
      ),
    ),
  );
  app.post(
    "/api/users",
    auth,
    role("admin"),
    asyncRoute(async (req, res) => {
      const values = profile(req.body),
        username = R.text(req.body.username, "Tên đăng nhập", 50, true),
        password = R.text(req.body.password, "Mật khẩu", 128, true),
        userRole = req.body.role || "employee";
      if (!/^[A-Za-z0-9_]{3,50}$/.test(username) || password.length < 8)
        R.fail(
          400,
          "Tên đăng nhập từ 3–50 ký tự chữ/số/gạch dưới; mật khẩu ít nhất 8 ký tự",
        );
      if (!["admin", "employee", "customer"].includes(userRole))
        R.fail(400, "Vai trò không hợp lệ");
      const hash = await bcrypt.hash(password, 12);
      const result = await store.transaction(async (ctx) => {
        if (
          (await ctx.list("Users")).some(
            (u) =>
              u.Username.toLowerCase() === username.toLowerCase() ||
              u.Email.toLowerCase() === values.Email ||
              (values.Phone && u.Phone === values.Phone),
          )
        )
          R.fail(409, "Tên đăng nhập, email hoặc số điện thoại đã tồn tại");
        const created = await ctx.insert("Users", {
          ...values,
          Username: username,
          PasswordHash: hash,
          Role: userRole,
          IsActive: true,
          CreatedAt: now(),
          UpdatedAt: now(),
        });
        await audit(
          ctx,
          req.user,
          "CREATE_USER",
          "User",
          created.Id,
          null,
          { Username: username, Role: userRole, FullName: values.FullName },
          req.ip,
        );
        return R.publicUser(created);
      });
      ok(res, result, 201);
    }),
  );
  app.put(
    "/api/users/:id",
    auth,
    role("admin"),
    mutation(async (ctx, req) => {
      const user = await ctx.get("Users", id(req.params.id));
      if (!user) R.fail(404, "Không tìm thấy người dùng");
      const values = { UpdatedAt: now() };
      if (req.body.role != null) {
        if (!["admin", "employee", "customer"].includes(req.body.role))
          R.fail(400, "Vai trò không hợp lệ");
        values.Role = req.body.role;
      }
      if (req.body.isActive != null) {
        if (typeof req.body.isActive !== "boolean")
          R.fail(400, "Trạng thái tài khoản không hợp lệ");
        values.IsActive = req.body.isActive;
      }
      if (
        user.Id === req.user.Id &&
        ((values.Role && values.Role !== "admin") || values.IsActive === false)
      )
        R.fail(409, "Không thể tự hạ quyền hoặc khóa tài khoản đang sử dụng");
      const updated = await ctx.update("Users", user.Id, values);
      await audit(
        ctx,
        req.user,
        "UPDATE_USER",
        "User",
        user.Id,
        { Role: user.Role, IsActive: user.IsActive },
        { Role: updated.Role, IsActive: updated.IsActive },
        req.ip,
      );
      return R.publicUser(updated);
    }),
  );
  app.get(
    "/api/reports",
    auth,
    staff,
    asyncRoute(async (req, res) => {
      let start = new Date("2000-01-01T00:00:00Z"),
        end = new Date(now().getTime() + 1);
      if (req.query.startDate || req.query.endDate) {
        const interval = R.range(
          req.query.startDate,
          req.query.endDate,
          now(),
          true,
        );
        start = interval.start;
        end = interval.end;
      }
      const allOrders = await store.list("RentalOrders"),
        cars = await store.list("Cars"),
        allPayments = await store.list("Payments");
      const inRange = (v) => new Date(v) >= start && new Date(v) < end;
      const orders = allOrders.filter((o) => inRange(o.CreatedAt)),
        payments = allPayments.filter((p) => inRange(p.CreatedAt));
      const totalRevenue = payments
        .filter((p) => p.Status === "completed")
        .reduce(
          (s, p) =>
            s + (p.PaymentType === "refund" ? -1 : 1) * Number(p.Amount),
          0,
        );
      const revenueByMonth = Object.entries(
        payments
          .filter((p) => p.Status === "completed")
          .reduce((all, p) => {
            const month = new Date(p.CreatedAt).toISOString().slice(0, 7);
            all[month] =
              (all[month] || 0) +
              (p.PaymentType === "refund" ? -1 : 1) * Number(p.Amount);
            return all;
          }, {}),
      )
        .sort()
        .map(([month, revenue]) => ({ month, revenue }));
      const vehicleUtilization = cars.map((car) => {
        const carOrders = allOrders.filter((o) => o.CarId === car.Id),
          periodOrders = orders.filter((o) => o.CarId === car.Id);
        const rentedMs = carOrders
          .filter((o) => o.ActualPickupDate)
          .reduce(
            (total, o) =>
              total +
              Math.max(
                0,
                Math.min(
                  new Date(o.ActualReturnDate || now()).getTime(),
                  end.getTime(),
                ) -
                  Math.max(
                    new Date(o.ActualPickupDate).getTime(),
                    start.getTime(),
                  ),
              ),
            0,
          );
        const ids = new Set(carOrders.map((o) => o.Id));
        const revenue = payments
          .filter((p) => ids.has(p.OrderId) && p.Status === "completed")
          .reduce(
            (sum, p) =>
              sum + (p.PaymentType === "refund" ? -1 : 1) * Number(p.Amount),
            0,
          );
        return {
          carId: car.Id,
          carName: car.Name,
          licensePlate: car.LicensePlate,
          totalOrders: periodOrders.length,
          completedOrders: periodOrders.filter((o) => o.Status === "completed")
            .length,
          rentedDays: Math.round((rentedMs / R.DAY) * 100) / 100,
          utilizationRate: Math.min(
            100,
            Math.round((rentedMs / (end - start)) * 10000) / 100,
          ),
          revenue,
        };
      });
      ok(res, {
        startDate: start,
        endDate: end,
        totalOrders: orders.length,
        activeRentals: allOrders.filter(
          (o) => o.Status === "renting" && !o.ActualReturnDate,
        ).length,
        pendingOrders: orders.filter((o) => o.Status === "pending").length,
        completedOrders: orders.filter((o) => o.Status === "completed").length,
        totalRevenue,
        totalCars: cars.length,
        availableCars: cars.filter((c) => c.Status === "available").length,
        maintenanceCars: cars.filter((c) => c.Status === "maintenance").length,
        revenueByMonth,
        ordersByStatus: Object.fromEntries(
          [
            "pending",
            "confirmed",
            "renting",
            "completed",
            "cancelled",
            "rejected",
          ].map((s) => [s, orders.filter((o) => o.Status === s).length]),
        ),
        vehicleUtilization,
      });
    }),
  );
  const dist = path.join(__dirname, "../frontend/dist");
  if (fs.existsSync(path.join(dist, "index.html"))) {
    app.use(express.static(dist));
    app.get("*", (req, res, next) =>
      req.path.startsWith("/api/")
        ? next()
        : res.sendFile(path.join(dist, "index.html")),
    );
  }
  app.use((req, res) =>
    res.status(404).json({ success: false, message: "Không tìm thấy API" }),
  );
  app.use((error, req, res, next) => {
    if (error.type === "entity.parse.failed")
      return res
        .status(400)
        .json({ success: false, message: "JSON không hợp lệ" });
    if (error.type === "entity.too.large")
      return res
        .status(413)
        .json({ success: false, message: "Dữ liệu quá lớn" });
    let status = error.status || 500;
    if ([2601, 2627].includes(error.number)) status = 409;
    if (status >= 500) console.error("API error:", error.message);
    res.status(status).json({
      success: false,
      message:
        status === 500
          ? "Lỗi hệ thống. Vui lòng thử lại"
          : status === 409 && !error.status
            ? "Dữ liệu đã tồn tại"
            : error.message,
    });
  });
  return app;
}
module.exports = { createApp };
