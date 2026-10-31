const DAY = 86400000;
function fail(status, message) {
  throw Object.assign(new Error(message), { status });
}
function text(value, name, max = 1000, required = false) {
  if (value == null && !required) return "";
  if (
    typeof value !== "string" ||
    (required && !value.trim()) ||
    value.length > max
  )
    fail(400, `${name} không hợp lệ (tối đa ${max} ký tự)`);
  return value.trim();
}
function number(value, name, min = 0, max = 1e12) {
  if (
    typeof value === "boolean" ||
    value === "" ||
    value == null ||
    !Number.isFinite(Number(value)) ||
    Number(value) < min ||
    Number(value) > max
  )
    fail(400, `${name} không hợp lệ`);
  return Number(value);
}
function date(value, name) {
  if (typeof value !== "string")
    fail(400, `${name} phải là thời gian ISO hợp lệ có múi giờ`);
  const m = value.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})$/,
  );
  if (!m || !Number.isFinite(Date.parse(value)))
    fail(400, `${name} phải là thời gian ISO hợp lệ có múi giờ`);
  const [year, month, day, hour, minute, second] = m
    .slice(1, 7)
    .map((v) => Number(v || 0));
  if (
    year < 2000 ||
    year > 2100 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > new Date(Date.UTC(year, month, 0)).getUTCDate() ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  )
    fail(400, `${name} không hợp lệ`);
  return new Date(value);
}
function range(startDate, endDate, now, allowPast = false) {
  const start = date(startDate, "Ngày nhận"),
    end = date(endDate, "Ngày trả");
  if (end <= start) fail(400, "Ngày trả phải sau ngày nhận");
  if (!allowPast && start <= now)
    fail(400, "Ngày nhận phải sau thời điểm hiện tại");
  if (end - start > DAY * 366) fail(400, "Thời gian thuê tối đa 366 ngày");
  return { start, end };
}
function quote(car, start, end) {
  const days = Math.max(1, Math.ceil((end - start) / DAY));
  const baseAmount = Math.round(Number(car.DailyRate) * days);
  return {
    days,
    dailyRate: Number(car.DailyRate),
    baseAmount,
    depositAmount: Math.round(
      (baseAmount * Number(car.DepositRate ?? 30)) / 100,
    ),
    totalAmount: baseAmount,
  };
}
function overlaps(a, b, c, d) {
  return new Date(a) < new Date(d) && new Date(b) > new Date(c);
}
function active(o) {
  return (
    ["pending", "confirmed", "renting"].includes(o.Status) &&
    !o.ActualReturnDate
  );
}
function paid(payments, orderId) {
  return payments
    .filter((p) => p.OrderId === orderId && p.Status === "completed")
    .reduce(
      (s, p) => s + (p.PaymentType === "refund" ? -1 : 1) * Number(p.Amount),
      0,
    );
}
function publicUser(u) {
  return {
    id: u.Id,
    username: u.Username,
    fullName: u.FullName,
    email: u.Email,
    phone: u.Phone,
    role: u.Role,
    address: u.Address || "",
    isActive: !!u.IsActive,
  };
}
function escape(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
module.exports = {
  DAY,
  fail,
  text,
  number,
  date,
  range,
  quote,
  overlaps,
  active,
  paid,
  publicUser,
  escape,
};
