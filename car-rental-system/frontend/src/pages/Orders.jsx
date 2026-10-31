import React, { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  CarFront,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  RefreshCw,
  Search,
  Wallet,
  XCircle,
} from "lucide-react";
import { api, asList, openContract } from "../services/api";
import { useApp } from "../context/AppContext";
import {
  Modal,
  Field,
  Submit,
  Loading,
  Empty,
  ErrorBox,
  Badge,
} from "../components/UI";
import {
  money,
  dateTime,
  dateOnly,
  localDate,
  paymentLabel,
  feeLabel,
  statusLabel,
} from "../utils";
function ActionForm({ action, order, onClose, onDone }) {
  const { notify } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [fees, setFees] = useState([]);
  const names = {
    confirm: "Xác nhận đơn thuê",
    reject: "Từ chối đơn thuê",
    pickup: "Lập biên bản nhận xe",
    return: "Lập biên bản trả xe",
    complete: "Hoàn tất & quyết toán",
    cancel: "Hủy đơn thuê",
  };
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    let body = Object.fromEntries(new FormData(e.currentTarget));
    if (action === "pickup" || action === "return") {
      const dateField =
        action === "pickup" ? "actualPickupDate" : "actualReturnDate";
      body[dateField] = new Date(body[dateField]).toISOString();
      body.odometerKm = Number(body.odometerKm);
      if (action === "return") {
        body.needsMaintenance = body.needsMaintenance === "on";
        body.extraFees = fees.map((f) => ({ ...f, amount: Number(f.amount) }));
      }
    }
    try {
      await api.put(`/orders/${order.Id}/${action}`, body);
      notify("Cập nhật đơn thuê thành công.");
      onDone();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={names[action]}
      subtitle={`Đơn ${order.OrderCode} · ${order.CarName}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="modal-body form-stack">
        {action === "confirm" && (
          <div className="info-note">
            <FileText size={22} />
            <span>
              Hệ thống kiểm tra lại lịch xe và tạo hợp đồng khi xác nhận. Khách
              hàng cần thanh toán đủ cọc trước khi nhận xe.
            </span>
          </div>
        )}
        {["cancel", "reject"].includes(action) && (
          <>
            <div className="info-note warning">
              <XCircle size={22} />
              <span>
                {action === "cancel" && order.Status === "confirmed"
                  ? `Phí hủy sau xác nhận: ${money(Math.round(Number(order.DepositAmount) * 0.5))}. Khoản đã thanh toán vượt phí hủy cần được nhân viên hoàn tiền.`
                  : "Lịch xe sẽ được giải phóng khi xử lý thành công."}
              </span>
            </div>
            <Field label={action === "cancel" ? "Lý do hủy" : "Lý do từ chối"}>
              <textarea
                name="reason"
                required
                rows={3}
                maxLength={1000}
                placeholder="Ghi rõ lý do xử lý đơn…"
              />
            </Field>
          </>
        )}
        {["pickup", "return"].includes(action) && (
          <>
            <Field
              label={
                action === "pickup"
                  ? "Thời điểm nhận xe thực tế"
                  : "Thời điểm trả xe thực tế"
              }
            >
              <input
                name={
                  action === "pickup" ? "actualPickupDate" : "actualReturnDate"
                }
                type="datetime-local"
                required
                defaultValue={localDate()}
                max={localDate(new Date(Date.now() + 5 * 60000))}
              />
            </Field>
            <Field label="Tình trạng xe">
              <textarea
                name="condition"
                required
                rows={3}
                minLength={3}
                maxLength={2000}
                placeholder="Ngoại thất, nội thất, các vết trầy xước, giấy tờ…"
              />
            </Field>
            <div className="form-grid">
              <Field label="Số km đồng hồ">
                <input
                  name="odometerKm"
                  type="number"
                  min={
                    action === "return" ? order.handover?.OdometerKm || 0 : 0
                  }
                  step="1"
                  required
                  defaultValue={order.handover?.OdometerKm || 0}
                />
              </Field>
              <Field label="Mức nhiên liệu">
                <select name="fuelLevel" required>
                  <option value="100%">Đầy bình (100%)</option>
                  <option value="75%">75%</option>
                  <option value="50%">50%</option>
                  <option value="25%">25%</option>
                  <option value="0%">0%</option>
                </select>
              </Field>
            </div>
            <Field label="Ghi chú">
              <textarea name="notes" rows={2} maxLength={1000} />
            </Field>
            {action === "return" && (
              <>
                <label className="checkbox-row">
                  <input name="needsMaintenance" type="checkbox" />
                  Xe cần bảo trì sau chuyến đi
                </label>
                <div className="fees-heading">
                  <strong>Phí phát sinh</strong>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      setFees([
                        ...fees,
                        { type: "damage", amount: "", reason: "" },
                      ])
                    }
                  >
                    + Thêm khoản phí
                  </button>
                </div>
                <p className="subtle">
                  Phí trả trễ do hệ thống tính tự động theo giờ trả thực tế.
                </p>
                {fees.map((fee, i) => (
                  <div className="fee-entry" key={i}>
                    <select
                      value={fee.type}
                      aria-label="Loại phí"
                      onChange={(e) =>
                        setFees(
                          fees.map((f, j) =>
                            i === j ? { ...f, type: e.target.value } : f,
                          ),
                        )
                      }
                    >
                      {["damage", "fuel", "cleaning", "other"].map((type) => (
                        <option value={type} key={type}>
                          {feeLabel[type]}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label="Số tiền phí"
                      type="number"
                      min="1"
                      step="1"
                      required
                      value={fee.amount}
                      placeholder="Số tiền"
                      onChange={(e) =>
                        setFees(
                          fees.map((f, j) =>
                            i === j ? { ...f, amount: e.target.value } : f,
                          ),
                        )
                      }
                    />
                    <input
                      aria-label="Lý do phát sinh phí"
                      required
                      maxLength={1000}
                      value={fee.reason}
                      placeholder="Lý do"
                      onChange={(e) =>
                        setFees(
                          fees.map((f, j) =>
                            i === j ? { ...f, reason: e.target.value } : f,
                          ),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="icon-button danger-text"
                      aria-label="Xóa phí"
                      onClick={() => setFees(fees.filter((_, j) => i !== j))}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </>
            )}
          </>
        )}
        {action === "complete" && (
          <div className="info-note">
            <CheckCircle2 size={23} />
            <span>
              Chỉ hoàn tất khi đã lập biên bản trả xe và đã thanh toán đủ{" "}
              {money(order.TotalAmount)}. Hợp đồng và lịch sử thuê sẽ được lưu
              để đối chiếu.
            </span>
          </div>
        )}
        {error && <ErrorBox message={error} />}
        <div className="form-actions">
          <button type="button" className="btn outline" onClick={onClose}>
            Quay lại
          </button>
          <Submit
            busy={busy}
            className={`btn ${["cancel", "reject"].includes(action) ? "danger" : "primary"}`}
          >
            {names[action]}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}
function PaymentForm({ order, onClose, onDone }) {
  const { isStaff, notify } = useApp();
  const [type, setType] = useState(
      isStaff &&
        Number(order.PaidAmount || order.TotalPaid || 0) >
          Number(order.TotalAmount)
        ? "refund"
        : order.Status === "cancelled"
          ? "full_payment"
          : Number(order.PaidAmount || order.TotalPaid || 0) <
              Number(order.DepositAmount)
            ? "deposit"
            : "full_payment",
    ),
    [failed, setFailed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const paid = Number(order.PaidAmount ?? order.TotalPaid ?? 0),
    balance = Number(order.BalanceDue ?? Math.max(0, order.TotalAmount - paid));
  const defaultAmount =
    type === "refund"
      ? Math.max(0, paid - Number(order.TotalAmount))
      : type === "deposit"
        ? Math.max(0, Number(order.DepositAmount) - paid)
        : balance;
  const [amount, setAmount] = useState(defaultAmount);
  const paymentKey = useRef(crypto.randomUUID());
  useEffect(() => setAmount(defaultAmount), [type]);
  useEffect(() => {
    paymentKey.current = crypto.randomUUID();
  }, [amount, type, failed]);
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const payment = await api.post("/payments", {
        orderId: order.Id,
        amount: Number(amount),
        paymentType: type,
        method: "simulation",
        simulateFailure: failed,
        idempotencyKey: paymentKey.current,
      });
      if (payment.Status === "failed") {
        notify(
          "Giao dịch mô phỏng thất bại. Số dư đơn thuê không thay đổi.",
          "error",
        );
        onDone();
        onClose();
      } else {
        notify(
          type === "refund"
            ? "Đã ghi nhận hoàn tiền mô phỏng."
            : "Thanh toán mô phỏng thành công.",
        );
        onDone();
        onClose();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Thanh toán mô phỏng"
      subtitle="Không kết nối ngân hàng và không thu tiền thật."
      onClose={onClose}
    >
      <form onSubmit={submit} className="modal-body form-stack">
        <div className="payment-amount-card">
          <Wallet size={26} />
          <div>
            <span>Còn phải thanh toán</span>
            <strong>{money(balance)}</strong>
          </div>
        </div>
        <Field label="Nội dung thanh toán">
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {order.Status !== "cancelled" && (
              <option value="deposit">Thanh toán cọc</option>
            )}
            <option value="full_payment">
              {order.Status === "cancelled"
                ? "Thanh toán phí hủy"
                : "Thanh toán tiền thuê còn lại"}
            </option>
            {isStaff && <option value="refund">Hoàn tiền cho khách</option>}
          </select>
        </Field>
        <Field label="Số tiền (VNĐ)">
          <input
            type="number"
            required
            min="1"
            step="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={failed}
            onChange={(e) => setFailed(e.target.checked)}
          />
          Mô phỏng giao dịch thất bại
        </label>
        <div className="info-note">
          <Shield size={20} />
          <span>
            Chỉ giao dịch thành công được tính vào tiền đã trả. Yêu cầu được xử
            lý chống ghi nhận lặp.
          </span>
        </div>
        {error && <ErrorBox message={error} />}
        <Submit busy={busy} disabled={Number(amount) <= 0}>
          {type === "refund" ? "Xác nhận hoàn tiền" : "Xác nhận thanh toán"}
          <ArrowRight size={17} />
        </Submit>
      </form>
    </Modal>
  );
}
function Shield(props) {
  return <CheckCircle2 {...props} />;
}
export function OrderDetail({ id, onClose, onChanged }) {
  const { user, isStaff, notify } = useApp();
  const [order, setOrder] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [action, setAction] = useState(null),
    [payment, setPayment] = useState(false),
    [editTerms, setEditTerms] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOrder(await api.get(`/orders/${id}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);
  function changed() {
    load();
    onChanged?.();
  }
  const returned = order?.ActualReturnDate;
  const status =
    returned && order?.Status === "renting" ? "Đã trả · chờ quyết toán" : null;
  const payments = asList(order?.payments);
  const paid = Number(
    order?.PaidAmount ??
      order?.TotalPaid ??
      payments
        .filter((p) => p.Status === "completed")
        .reduce(
          (sum, p) =>
            sum + (p.PaymentType === "refund" ? -1 : 1) * Number(p.Amount),
          0,
        ),
  );
  const outstanding = Math.max(0, Number(order?.TotalAmount || 0) - paid);
  async function contract() {
    try {
      await openContract(id);
    } catch (err) {
      notify(err.message, "error");
    }
  }
  return (
    <>
      <Modal
        title={order?.OrderCode || "Chi tiết đơn thuê"}
        subtitle={
          order
            ? `${order.CarName} · ${order.LicensePlate || ""}`
            : "Thông tin hành trình"
        }
        onClose={onClose}
        wide
      >
        {loading ? (
          <Loading />
        ) : error ? (
          <div className="modal-body">
            <ErrorBox message={error} onRetry={load} />
          </div>
        ) : (
          order && (
            <div className="order-detail-body">
              <div className="order-detail-top">
                <div>
                  <Badge status={order.Status}>{status}</Badge>
                  <Badge
                    status={
                      order.PaymentStatus ||
                      (paid >= order.TotalAmount
                        ? "paid"
                        : paid > 0
                          ? "partial"
                          : "unpaid")
                    }
                  />
                </div>
                <button
                  className="btn outline small"
                  onClick={contract}
                  disabled={
                    order.Status === "pending" || order.Status === "rejected"
                  }
                >
                  <FileText size={16} />
                  Xem / in hợp đồng
                </button>
              </div>
              <div className="order-timeline">
                {[
                  { title: "Tạo đơn", done: true },
                  {
                    title: "Xác nhận",
                    done: !["pending", "rejected", "cancelled"].includes(
                      order.Status,
                    ),
                  },
                  { title: "Nhận xe", done: !!order.ActualPickupDate },
                  { title: "Trả xe", done: !!order.ActualReturnDate },
                  { title: "Hoàn tất", done: order.Status === "completed" },
                ].map((step, i) => (
                  <div className={step.done ? "done" : ""} key={step.title}>
                    <span>
                      {step.done ? <CheckCircle2 size={20} /> : i + 1}
                    </span>
                    <small>{step.title}</small>
                  </div>
                ))}
              </div>
              <div className="order-detail-grid">
                <div>
                  <section className="detail-section">
                    <h3>
                      <CarFront size={18} />
                      Thông tin thuê xe
                    </h3>
                    <dl>
                      <div>
                        <dt>Khách hàng</dt>
                        <dd>{order.CustomerName || user.fullName}</dd>
                      </div>
                      <div>
                        <dt>Xe</dt>
                        <dd>{order.CarName}</dd>
                      </div>
                      <div>
                        <dt>Nhận xe dự kiến</dt>
                        <dd>{dateTime(order.StartDate)}</dd>
                      </div>
                      <div>
                        <dt>Trả xe dự kiến</dt>
                        <dd>{dateTime(order.EndDate)}</dd>
                      </div>
                      <div>
                        <dt>Ngày tạo đơn</dt>
                        <dd>{dateTime(order.CreatedAt)}</dd>
                      </div>
                      {order.Notes && (
                        <div>
                          <dt>Ghi chú</dt>
                          <dd>{order.Notes}</dd>
                        </div>
                      )}
                      {order.CancellationReason && (
                        <div>
                          <dt>Lý do hủy</dt>
                          <dd>{order.CancellationReason}</dd>
                        </div>
                      )}
                    </dl>
                  </section>
                  {(order.ActualPickupDate || order.handover) && (
                    <section className="detail-section">
                      <h3>
                        <CheckCircle2 size={18} />
                        Biên bản nhận xe
                      </h3>
                      <dl>
                        <div>
                          <dt>Thời điểm thực tế</dt>
                          <dd>
                            {dateTime(
                              order.ActualPickupDate ||
                                order.handover?.HandoverAt,
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>Tình trạng</dt>
                          <dd>
                            {order.PickupCondition ||
                              order.handover?.VehicleCondition}
                          </dd>
                        </div>
                        <div>
                          <dt>Đồng hồ / nhiên liệu</dt>
                          <dd>
                            {order.handover?.OdometerKm ?? "—"} km /{" "}
                            {order.handover?.FuelLevel || "—"}
                          </dd>
                        </div>
                      </dl>
                    </section>
                  )}
                  {returned && (
                    <section className="detail-section">
                      <h3>
                        <CheckCircle2 size={18} />
                        Biên bản trả xe
                      </h3>
                      <dl>
                        <div>
                          <dt>Thời điểm thực tế</dt>
                          <dd>{dateTime(order.ActualReturnDate)}</dd>
                        </div>
                        <div>
                          <dt>Tình trạng</dt>
                          <dd>
                            {order.ReturnCondition ||
                              order.return?.VehicleCondition}
                          </dd>
                        </div>
                        <div>
                          <dt>Đồng hồ / nhiên liệu</dt>
                          <dd>
                            {order.return?.OdometerKm ?? "—"} km /{" "}
                            {order.return?.FuelLevel || "—"}
                          </dd>
                        </div>
                      </dl>
                    </section>
                  )}
                  {asList(order.extraFees).length > 0 && (
                    <section className="detail-section">
                      <h3>Chi tiết phí phát sinh</h3>
                      {asList(order.extraFees).map((f, i) => (
                        <div className="fee-display" key={i}>
                          <span>
                            {feeLabel[f.FeeType] || f.FeeType}
                            <small>{f.Reason}</small>
                          </span>
                          <strong>{money(f.Amount)}</strong>
                        </div>
                      ))}
                    </section>
                  )}
                </div>
                <div>
                  <section className="detail-section invoice">
                    <h3>
                      <Wallet size={18} />
                      Tổng kết chi phí
                    </h3>
                    <dl>
                      <div>
                        <dt>Tiền thuê cơ bản</dt>
                        <dd>{money(order.BaseAmount)}</dd>
                      </div>
                      <div>
                        <dt>Cọc yêu cầu (đã gồm trong giá)</dt>
                        <dd>{money(order.DepositAmount)}</dd>
                      </div>
                      {Number(order.LateFee) > 0 && (
                        <div>
                          <dt>Phí trả trễ</dt>
                          <dd>{money(order.LateFee)}</dd>
                        </div>
                      )}
                      {Number(order.TotalExtraFee) > 0 && (
                        <div>
                          <dt>Phí phát sinh khác</dt>
                          <dd>
                            {money(
                              Math.max(
                                0,
                                Number(order.TotalExtraFee) -
                                  Number(order.LateFee || 0),
                              ),
                            )}
                          </dd>
                        </div>
                      )}
                      {Number(order.CancellationFee) > 0 && (
                        <div>
                          <dt>Phí hủy</dt>
                          <dd>{money(order.CancellationFee)}</dd>
                        </div>
                      )}
                      <div className="invoice-total">
                        <dt>Tổng phải trả</dt>
                        <dd>{money(order.TotalAmount)}</dd>
                      </div>
                      <div>
                        <dt>Đã thanh toán ròng</dt>
                        <dd className="green-text">{money(paid)}</dd>
                      </div>
                      <div className="invoice-balance">
                        <dt>Còn lại</dt>
                        <dd>{money(outstanding)}</dd>
                      </div>
                    </dl>
                    {paid > Number(order.TotalAmount) && (
                      <div className="info-note">
                        <Wallet size={18} />
                        <span>
                          Cần hoàn lại {money(paid - Number(order.TotalAmount))}{" "}
                          cho khách. Nhân viên sẽ xử lý hoàn tiền mô phỏng.
                        </span>
                      </div>
                    )}
                    {!["rejected"].includes(order.Status) &&
                      ((order.Status !== "completed" && outstanding > 0) ||
                        (isStaff && paid > Number(order.TotalAmount))) && (
                        <button
                          className="btn primary full"
                          onClick={() => setPayment(true)}
                        >
                          <Wallet size={17} />
                          {paid > order.TotalAmount
                            ? "Hoàn tiền chênh lệch"
                            : "Thanh toán mô phỏng"}
                        </button>
                      )}
                  </section>
                  <section className="detail-section">
                    <h3>Lịch sử thanh toán</h3>
                    {payments.length ? (
                      payments.map((p) => (
                        <div className="payment-row" key={p.Id}>
                          <div>
                            <strong>
                              {paymentLabel[p.PaymentType] || p.PaymentType}
                            </strong>
                            <small>{dateTime(p.CreatedAt)}</small>
                          </div>
                          <div>
                            <strong>
                              {p.PaymentType === "refund" ? "-" : ""}
                              {money(p.Amount)}
                            </strong>
                            <Badge status={p.Status} />
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="subtle">Chưa có giao dịch.</p>
                    )}
                  </section>
                </div>
              </div>
              <div className="order-actions">
                {isStaff &&
                  order.Status === "confirmed" &&
                  !order.ActualPickupDate && (
                    <button
                      className="btn outline"
                      onClick={() => setEditTerms(true)}
                    >
                      <FileText size={16} />
                      Sửa điều khoản hợp đồng
                    </button>
                  )}
                {isStaff && order.Status === "pending" && (
                  <>
                    <button
                      className="btn primary"
                      onClick={() => setAction("confirm")}
                    >
                      Xác nhận đơn
                    </button>
                    <button
                      className="btn outline danger-text"
                      onClick={() => setAction("reject")}
                    >
                      Từ chối
                    </button>
                  </>
                )}
                {isStaff && order.Status === "confirmed" && (
                  <button
                    className="btn primary"
                    onClick={() => setAction("pickup")}
                  >
                    Lập biên bản nhận xe
                  </button>
                )}
                {isStaff && order.Status === "renting" && !returned && (
                  <button
                    className="btn primary"
                    onClick={() => setAction("return")}
                  >
                    Lập biên bản trả xe
                  </button>
                )}
                {isStaff && order.Status === "renting" && returned && (
                  <button
                    className="btn primary"
                    onClick={() => setAction("complete")}
                  >
                    Quyết toán & hoàn tất
                  </button>
                )}
                {["pending", "confirmed"].includes(order.Status) && (
                  <button
                    className="btn outline danger-text"
                    onClick={() => setAction("cancel")}
                  >
                    Hủy đơn thuê
                  </button>
                )}
                <button className="btn ghost" onClick={load}>
                  <RefreshCw size={16} />
                  Làm mới
                </button>
              </div>
              {order.Status === "confirmed" && (
                <p className="subtle">
                  Nhận xe từ thời điểm bắt đầu lịch thuê, sau khi thanh toán đủ
                  tiền cọc.
                </p>
              )}
            </div>
          )
        )}
      </Modal>
      {action && order && (
        <ActionForm
          action={action}
          order={order}
          onClose={() => setAction(null)}
          onDone={changed}
        />
      )}{" "}
      {editTerms && order && (
        <ContractEditor
          order={order}
          onClose={() => setEditTerms(false)}
          onDone={changed}
        />
      )}{" "}
      {payment && order && (
        <PaymentForm
          order={order}
          onClose={() => setPayment(false)}
          onDone={changed}
        />
      )}
    </>
  );
}
function ContractEditor({ order, onClose, onDone }) {
  const { notify } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.put(`/orders/${order.Id}/contract`, {
        terms: new FormData(e.currentTarget).get("terms"),
      });
      notify("Đã cập nhật điều khoản và thông báo cho khách.");
      onDone();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Điều khoản hợp đồng"
      subtitle="Chỉ cập nhật trước khi bàn giao xe. Mọi thay đổi được lưu nhật ký."
      onClose={onClose}
    >
      <form onSubmit={submit} className="modal-body form-stack">
        <Field label="Điều khoản bổ sung">
          <textarea
            name="terms"
            rows={8}
            required
            maxLength={10000}
            defaultValue={order.contract?.RentalTerms || ""}
          />
        </Field>
        {error && <ErrorBox message={error} />}
        <Submit busy={busy}>Lưu điều khoản</Submit>
      </form>
    </Modal>
  );
}
export default function Orders() {
  const { isStaff, refresh } = useApp();
  const [orders, setOrders] = useState([]),
    [status, setStatus] = useState(""),
    [search, setSearch] = useState(""),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [selected, setSelected] = useState(null);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setOrders(asList(await api.get("/orders")));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, [refresh]);
  const list = orders.filter(
    (o) =>
      (!status || o.Status === status) &&
      `${o.OrderCode} ${o.CarName} ${o.CustomerName || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <div className="container page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">THEO DÕI MỌI ĐIỂM CHẠM</p>
          <h1>{isStaff ? "Quản lý đơn thuê xe" : "Chuyến đi của tôi"}</h1>
          <p>
            {isStaff
              ? "Từ xác nhận đến bàn giao và quyết toán, mọi thao tác được ghi lại."
              : "Lịch trình, hợp đồng và thanh toán — tất cả ở một nơi."}
          </p>
        </div>
        <Link className="btn primary" to="/">
          Đặt thêm chuyến đi
          <ArrowUpRightIcon />
        </Link>
      </div>
      <div className="list-toolbar">
        <div className="tabs scroll-tabs">
          {[
            ["", "Tất cả"],
            ["pending", "Chờ xác nhận"],
            ["confirmed", "Đã xác nhận"],
            ["renting", "Đang thuê / chờ chốt"],
            ["completed", "Hoàn tất"],
            ["cancelled", "Đã hủy"],
            ["rejected", "Từ chối"],
          ].map(([key, label]) => (
            <button
              className={status === key ? "active" : ""}
              key={key}
              onClick={() => setStatus(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="input-icon">
          <Search size={17} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm mã đơn, xe…"
          />
        </div>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : list.length ? (
        <div className="order-list">
          {list.map((order) => (
            <button
              className="order-card"
              onClick={() => setSelected(order.Id)}
              key={order.Id}
            >
              <div className="order-car-icon">
                <CarFront size={31} />
              </div>
              <div className="order-main">
                <div>
                  <span className="order-code">{order.OrderCode}</span>
                  <Badge status={order.Status}>
                    {order.ActualReturnDate && order.Status === "renting"
                      ? "Đã trả · chờ quyết toán"
                      : null}
                  </Badge>
                </div>
                <h3>{order.CarName}</h3>
                <p>
                  <CalendarDays size={15} />
                  {dateTime(order.StartDate)}
                  <ArrowRight size={13} />
                  {dateTime(order.EndDate)}
                </p>
                {isStaff && <small>{order.CustomerName}</small>}
              </div>
              <div className="order-right">
                <strong>{money(order.TotalAmount)}</strong>
                <span>{order.LicensePlate}</span>
                <span className="order-detail-link">
                  Xem chi tiết
                  <ChevronRight size={15} />
                </span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <Empty
          title={
            status
              ? "Không có đơn trong trạng thái này"
              : "Hành trình tiếp theo đang chờ bạn"
          }
          text="Tìm chiếc xe phù hợp và lên lịch cho chuyến đi của mình."
          action={
            <Link className="btn primary" to="/">
              Khám phá xe
              <ArrowRight size={17} />
            </Link>
          }
        />
      )}{" "}
      {selected && (
        <OrderDetail
          id={selected}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      )}
    </div>
  );
}
function ArrowUpRightIcon() {
  return <ArrowRight size={17} />;
}
