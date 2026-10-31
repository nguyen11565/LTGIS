export const money = (value) =>
  new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
export const dateTime = (value) =>
  value
    ? new Date(value).toLocaleString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
export const dateOnly = (value) =>
  value
    ? new Date(value).toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "—";
export const localDate = (value) => {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
export const defaultDates = () => {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(9, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 3);
  return { start: localDate(start), end: localDate(end) };
};
export function validDates(start, end) {
  if (
    !start ||
    !end ||
    !Number.isFinite(new Date(start).getTime()) ||
    !Number.isFinite(new Date(end).getTime())
  )
    return "Vui lòng chọn đầy đủ ngày, giờ nhận và trả xe.";
  if (new Date(end) <= new Date(start))
    return "Thời điểm trả xe phải sau thời điểm nhận xe.";
  if (new Date(start) <= new Date())
    return "Thời điểm nhận xe phải ở tương lai.";
  return "";
}
export const statusLabel = {
  pending: "Chờ xác nhận",
  confirmed: "Đã xác nhận",
  renting: "Đang thuê",
  completed: "Hoàn tất",
  cancelled: "Đã hủy",
  rejected: "Đã từ chối",
  available: "Sẵn sàng",
  booked: "Đã có lịch đặt",
  maintenance: "Bảo trì",
  suspended: "Tạm ngưng",
  unpaid: "Chưa thanh toán",
  partial: "Thanh toán một phần",
  paid: "Đã thanh toán",
  refunded: "Đã hoàn tiền",
  failed: "Thất bại",
  active: "Hiệu lực",
  draft: "Bản nháp",
};
export const roleLabel = {
  customer: "Khách hàng",
  employee: "Nhân viên",
  admin: "Quản trị viên",
};
export const paymentLabel = {
  deposit: "Đặt cọc",
  full_payment: "Thanh toán tiền thuê",
  refund: "Hoàn tiền",
  extra_fee: "Phí phát sinh",
  cancellation_fee: "Phí hủy đơn",
};
export const feeLabel = {
  damage: "Hư hỏng",
  fuel: "Nhiên liệu",
  cleaning: "Vệ sinh",
  other: "Khác",
  late: "Trả trễ",
};
export const value = (entity, Pascal, camel) =>
  entity?.[Pascal] ??
  entity?.[camel || Pascal.charAt(0).toLowerCase() + Pascal.slice(1)];
export const transmissionLabel = (v) =>
  ({ automatic: "Tự động", manual: "Số sàn" })[v] || v || "Tự động";
export const fuelLabel = (v) =>
  ({
    gasoline: "Xăng",
    diesel: "Dầu diesel",
    electric: "Điện",
    hybrid: "Hybrid",
  })[v] ||
  v ||
  "Xăng";
