// Isolated browser test: explicit memory store, never connects to or alters a real database.
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { mkdir } = require("node:fs/promises");
const path = require("node:path");
const { existsSync } = require("node:fs");
const { chromium } = require("playwright");
const { createApp } = require("../backend/app");
const { createDemoState } = require("../backend/seedData");
const { createMemoryStore } = require("../backend/storage/memory");
const root = path.resolve(__dirname, "..");
const apiBase = "http://127.0.0.1:5101/api",
  site = "http://127.0.0.1:5176";
const screenshotDir =
  process.env.SCREENSHOT_DIR || path.join(root, "docs/screenshots");
function localDate(value) {
  return new Date(new Date(value).getTime() + 7 * 3600000)
    .toISOString()
    .slice(0, 16);
}
async function main() {
  let server, vite, browser;
  const failures = [];
  try {
    const now = Date.now();
    let clock = new Date(now - 8 * 3600000);
    const store = createMemoryStore(await createDemoState());
    const app = createApp({
      store,
      jwtSecret: "isolated-browser-test-secret-over-24-chars",
      clock: () => clock,
      corsOrigin: site,
    });
    server = await new Promise((resolve) => {
      const s = app.listen(5101, "127.0.0.1", () => resolve(s));
    });
    async function api(url, method = "GET", body, token) {
      const r = await fetch(apiBase + url, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      const j = await r.json();
      assert.ok(r.ok, j.message || url);
      return j.data;
    }
    const customer = await api("/auth/login", "POST", {
      username: "customer",
      password: "Customer@123",
    });
    const employee = await api("/auth/login", "POST", {
      username: "employee",
      password: "Employee@123",
    });
    const fixture = await api(
      "/orders",
      "POST",
      {
        carId: 1,
        startDate: new Date(now - 6 * 3600000).toISOString(),
        endDate: new Date(now - 4 * 3600000).toISOString(),
        notes: "Isolated browser pickup/late return fixture",
      },
      customer.token,
    );
    await api(`/orders/${fixture.Id}/confirm`, "PUT", {}, employee.token);
    await api(
      "/payments",
      "POST",
      {
        orderId: fixture.Id,
        amount: fixture.DepositAmount,
        paymentType: "deposit",
        method: "simulation",
        idempotencyKey: "browser-fixture-deposit",
      },
      customer.token,
    );
    clock = new Date(now);
    vite = spawn(
      process.execPath,
      [
        path.join(root, "frontend/node_modules/vite/bin/vite.js"),
        "--host",
        "127.0.0.1",
        "--port",
        "5176",
        "--strictPort",
      ],
      {
        cwd: path.join(root, "frontend"),
        env: { ...process.env, VITE_API_URL: apiBase },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    vite.on("error", (e) => failures.push(e.message));
    let ready = false;
    for (let i = 0; i < 50; i++) {
      try {
        if ((await fetch(site)).ok) {
          ready = true;
          break;
        }
      } catch {}
      await new Promise((r) => setTimeout(r, 100));
    }
    assert.ok(ready, "Vite ready");
    browser = await chromium.launch({
      executablePath:
        process.env.CHROMIUM_PATH ||
        (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined),
      headless: true,
      args: ["--no-sandbox"],
    });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
      timezoneId: "Asia/Ho_Chi_Minh",
    });
    page.on("pageerror", (e) => failures.push(e.message));
    await mkdir(screenshotDir, { recursive: true });
    const dialog = () => page.getByRole("dialog").last();
    async function login(username, password) {
      await page.goto(site);
      await page.evaluate(() => localStorage.removeItem("lai-viet-token"));
      await page.reload();
      await page
        .getByRole("button", { name: "Đăng nhập", exact: true })
        .first()
        .click();
      await dialog().getByLabel("Tên đăng nhập").fill(username);
      await dialog().getByLabel("Mật khẩu", { exact: false }).fill(password);
      await dialog()
        .getByRole("button", { name: "Đăng nhập", exact: true })
        .last()
        .click();
      await page.getByRole("dialog").waitFor({ state: "hidden" });
    }
    async function openOrder(code) {
      await page.goto(site + "/orders");
      await page.locator(".order-card").filter({ hasText: code }).click();
      await dialog().getByText("Tổng kết chi phí").waitFor();
    }
    await page.goto(site);
    await page
      .getByRole("button", { name: "Xem Toyota Vios", exact: true })
      .waitFor();
    await page.screenshot({
      path: path.join(screenshotDir, "catalog-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: path.join(screenshotDir, "catalog-mobile.png"),
      fullPage: true,
    });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "No mobile horizontal overflow",
    );
    await page.setViewportSize({ width: 1440, height: 1000 });
    console.log("PASS catalog desktop/mobile, no overflow");
    await login("customer", "Customer@123");
    await page
      .getByRole("button", { name: "Xem Mazda CX-5", exact: true })
      .click();
    await dialog().getByRole("button", { name: "Kiểm tra lịch & giá" }).click();
    await dialog().getByText("Xe còn trống trong lịch bạn chọn").waitFor();
    const created = page.waitForResponse(
      (r) => r.url() === apiBase + "/orders" && r.request().method() === "POST",
    );
    await dialog()
      .getByRole("button", { name: "Xác nhận đặt xe", exact: true })
      .click();
    const booked = (await (await created).json()).data;
    assert.ok(booked.Id);
    await openOrder(booked.OrderCode);
    await dialog()
      .getByRole("button", { name: "Thanh toán mô phỏng", exact: true })
      .click();
    await dialog().getByLabel("Mô phỏng giao dịch thất bại").check();
    await dialog().getByRole("button", { name: "Xác nhận thanh toán" }).click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Thanh toán mô phỏng",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    let loaded = await api(`/orders/${booked.Id}`, "GET", null, customer.token);
    assert.equal(loaded.TotalPaid, 0);
    assert.equal(loaded.payments[0].Status, "failed");
    await dialog()
      .getByRole("button", { name: "Thanh toán mô phỏng", exact: true })
      .click();
    await dialog().getByRole("button", { name: "Xác nhận thanh toán" }).click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Thanh toán mô phỏng",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    loaded = await api(`/orders/${booked.Id}`, "GET", null, customer.token);
    assert.equal(loaded.TotalPaid, booked.DepositAmount);
    console.log(
      "PASS customer UI booking, failed payment no credit, successful deposit",
    );
    await login("employee", "Employee@123");
    await openOrder(booked.OrderCode);
    await dialog()
      .getByRole("button", { name: "Xác nhận đơn", exact: true })
      .click();
    await dialog()
      .getByRole("button", { name: "Xác nhận đơn thuê", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Xác nhận đơn thuê",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    const popupPromise = page.waitForEvent("popup");
    await dialog().getByRole("button", { name: "Xem / in hợp đồng" }).click();
    const popup = await popupPromise;
    await popup
      .getByRole("heading", { name: "HỢP ĐỒNG THUÊ XE DU LỊCH" })
      .waitFor();
    await popup.close();
    console.log("PASS staff confirm, generated printable contract");
    await openOrder(fixture.OrderCode);
    await dialog()
      .getByRole("button", { name: "Lập biên bản nhận xe", exact: true })
      .click();
    await dialog()
      .getByLabel("Thời điểm nhận xe thực tế")
      .fill(localDate(now - 5 * 3600000));
    await dialog()
      .getByLabel("Tình trạng xe")
      .fill("Xe nguyên vẹn, đủ giấy tờ");
    await dialog().getByLabel("Số km đồng hồ").fill("12000");
    await dialog()
      .getByRole("button", { name: "Lập biên bản nhận xe", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Lập biên bản nhận xe",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    await dialog()
      .getByRole("button", { name: "Lập biên bản trả xe", exact: true })
      .click();
    await dialog()
      .getByLabel("Tình trạng xe")
      .fill("Xe sạch, trả trễ, có phát sinh vệ sinh");
    await dialog().getByLabel("Số km đồng hồ").fill("12200");
    await dialog().getByRole("button", { name: "+ Thêm khoản phí" }).click();
    await dialog().getByLabel("Số tiền phí").fill("100000");
    await dialog()
      .getByLabel("Lý do phát sinh phí")
      .fill("Vệ sinh nội thất theo biên bản");
    await dialog()
      .getByRole("button", { name: "Lập biên bản trả xe", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Lập biên bản trả xe",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    loaded = await api(`/orders/${fixture.Id}`, "GET", null, employee.token);
    assert.equal(loaded.LateFee, 975000);
    assert.equal(loaded.TotalExtraFee, 1075000);
    assert.ok(loaded.ActualReturnDate);
    await dialog()
      .getByRole("button", { name: "Thanh toán mô phỏng", exact: true })
      .click();
    await dialog().getByRole("button", { name: "Xác nhận thanh toán" }).click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Thanh toán mô phỏng",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    await dialog()
      .getByRole("button", { name: "Quyết toán & hoàn tất" })
      .click();
    await dialog()
      .getByRole("button", { name: "Hoàn tất & quyết toán" })
      .click();
    await page
      .getByRole("dialog")
      .filter({
        has: page.getByRole("heading", {
          name: "Hoàn tất & quyết toán",
          exact: true,
        }),
      })
      .waitFor({ state: "hidden" });
    loaded = await api(`/orders/${fixture.Id}`, "GET", null, employee.token);
    assert.equal(loaded.Status, "completed");
    await page.screenshot({
      path: path.join(screenshotDir, "completed-order.png"),
      fullPage: true,
    });
    console.log(
      "PASS staff UI pickup, late return, extra fee, settlement, completed",
    );
    await login("admin", "Admin@123");
    await page
      .getByRole("heading", { name: "Bảng điều hành", exact: true })
      .waitFor();
    await page.getByRole("heading", { name: "Tổng quan vận hành" }).waitFor();
    await page.screenshot({
      path: path.join(screenshotDir, "admin-dashboard.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Người dùng", exact: true }).click();
    await page
      .getByRole("button", { name: "Tạo tài khoản", exact: true })
      .click();
    await dialog().getByLabel("Họ và tên").fill("Nhân viên kiểm thử");
    await dialog().getByLabel("Tên đăng nhập").fill("browser_staff");
    await dialog().getByLabel("Email").fill("browser_staff@example.com");
    await dialog().getByLabel("Số điện thoại").fill("0911223344");
    await dialog().getByLabel("Mật khẩu khởi tạo").fill("Browser@123");
    await dialog()
      .getByRole("button", { name: "Tạo tài khoản", exact: true })
      .click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page.getByText("@browser_staff", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Nhật ký", exact: true }).click();
    await page
      .getByRole("button", { name: "Chi tiết", exact: true })
      .first()
      .click();
    await dialog().getByRole("heading", { name: "Chi tiết nhật ký" }).waitFor();
    assert.ok((await dialog().innerText()).includes("Dữ liệu sau"));
    await dialog().getByRole("button", { name: "Đóng", exact: true }).click();
    console.log("PASS admin dashboard/users/audit detail");
    await login("customer", "Customer@123");
    await page.goto(site + "/notifications");
    await page
      .getByText("Đơn thuê đã xác nhận", { exact: true })
      .first()
      .waitFor();
    console.log("PASS customer notifications");
    assert.deepEqual(failures, [], "No browser JS errors");
    console.log(
      "BROWSER SMOKE PASS (isolated memory adapter; not SQL validation)",
    );
  } finally {
    if (browser) await browser.close();
    if (vite)
      await new Promise((resolve) => {
        vite.once("exit", resolve);
        vite.kill("SIGTERM");
        setTimeout(resolve, 2000).unref();
      });
    if (server) await new Promise((r) => server.close(r));
  }
}
main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
