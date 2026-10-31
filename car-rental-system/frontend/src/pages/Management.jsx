import React, { useState, useEffect } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  CarFront,
  CheckCircle2,
  ClipboardList,
  FileClock,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import { api, asList } from "../services/api";
import { useApp } from "../context/AppContext";
import {
  Modal,
  Field,
  Submit,
  Loading,
  Empty,
  ErrorBox,
  Badge,
  CarImage,
} from "../components/UI";
import { money, dateTime, roleLabel, statusLabel } from "../utils";
import { Link } from "react-router-dom";
const carStatuses = ["available", "maintenance", "suspended"];
function CarForm({ car, onClose, onDone }) {
  const { notify } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const body = Object.fromEntries(new FormData(e.currentTarget));
    for (const k of ["dailyRate", "year", "seats", "depositRate"])
      body[k] = Number(body[k]);
    try {
      await (car ? api.put(`/cars/${car.Id}`, body) : api.post("/cars", body));
      notify(car ? "Đã cập nhật thông tin xe." : "Đã thêm xe vào đội xe.");
      onDone();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={car ? "Cập nhật thông tin xe" : "Thêm chiếc xe mới"}
      onClose={onClose}
      wide
    >
      <form onSubmit={submit} className="modal-body form-stack">
        <div className="form-grid">
          <Field label="Tên xe">
            <input
              name="name"
              defaultValue={car?.Name}
              required
              maxLength={100}
              placeholder="Toyota Vios 2024"
            />
          </Field>
          <Field label="Biển số">
            <input
              name="licensePlate"
              defaultValue={car?.LicensePlate}
              required
              maxLength={20}
              placeholder="30A-123.45"
            />
          </Field>
          <Field label="Hãng xe">
            <input
              name="brand"
              defaultValue={car?.Brand}
              required
              maxLength={50}
              placeholder="Toyota"
            />
          </Field>
          <Field label="Dòng xe">
            <input
              name="model"
              defaultValue={car?.Model}
              required
              maxLength={50}
              placeholder="Vios"
            />
          </Field>
          <Field label="Năm sản xuất">
            <input
              name="year"
              type="number"
              min="1990"
              max={new Date().getFullYear() + 1}
              defaultValue={car?.Year || 2024}
              required
            />
          </Field>
          <Field label="Số chỗ">
            <input
              name="seats"
              type="number"
              min="2"
              max="50"
              defaultValue={car?.Seats || 5}
              required
            />
          </Field>
          <Field label="Hộp số">
            <select
              name="transmission"
              defaultValue={car?.Transmission || "automatic"}
            >
              <option value="automatic">Tự động</option>
              <option value="manual">Số sàn</option>
            </select>
          </Field>
          <Field label="Nhiên liệu">
            <select name="fuelType" defaultValue={car?.FuelType || "gasoline"}>
              <option value="gasoline">Xăng</option>
              <option value="diesel">Dầu diesel</option>
              <option value="electric">Điện</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </Field>
          <Field label="Giá thuê / ngày (VNĐ)">
            <input
              name="dailyRate"
              type="number"
              min="1000"
              max="100000000"
              step="1000"
              defaultValue={car?.DailyRate || 700000}
              required
            />
          </Field>
          <Field
            label="Tỷ lệ đặt cọc (%)"
            hint="Tiền cọc được khấu trừ vào tổng tiền thuê."
          >
            <input
              name="depositRate"
              type="number"
              min="0"
              max="100"
              step="1"
              defaultValue={car?.DepositRate ?? 30}
              required
            />
          </Field>
        </div>
        <Field label="Ảnh xe (URL hoặc đường dẫn nội bộ)">
          <input
            name="imageUrl"
            defaultValue={car?.ImageUrl || "/images/car-sedan.svg"}
            maxLength={500}
            placeholder="https://…"
          />
        </Field>
        <Field label="Mô tả">
          <textarea
            name="description"
            defaultValue={car?.Description}
            rows={3}
            maxLength={2000}
          />
        </Field>
        {error && <ErrorBox message={error} />}
        <div className="form-actions">
          <button type="button" className="btn outline" onClick={onClose}>
            Quay lại
          </button>
          <Submit busy={busy}>Lưu thông tin xe</Submit>
        </div>
      </form>
    </Modal>
  );
}
function CarManagement() {
  const { notify, isAdmin } = useApp();
  const [cars, setCars] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [form, setForm] = useState(null),
    [search, setSearch] = useState(""),
    [busy, setBusy] = useState(null);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setCars(asList(await api.get("/cars")));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function changeStatus(car, status) {
    setBusy(car.Id);
    try {
      await api.put(`/cars/${car.Id}/status`, { status });
      notify("Đã cập nhật trạng thái xe.");
      load();
    } catch (e) {
      notify(e.message, "error");
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Đội xe của bạn</h2>
          <p>Thông tin, giá thuê và trạng thái vận hành.</p>
        </div>
        {isAdmin && (
          <button className="btn primary small" onClick={() => setForm("new")}>
            <Plus size={17} />
            Thêm xe
          </button>
        )}
      </div>
      <div className="list-toolbar">
        <div className="input-icon">
          <Search size={17} />
          <input
            placeholder="Tên xe hoặc biển số…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button className="btn ghost small" onClick={load}>
          <RefreshCw size={16} />
          Làm mới
        </button>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Xe / Biển số</th>
                <th>Thông số</th>
                <th>Giá / ngày</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {cars
                .filter((c) =>
                  `${c.Name} ${c.LicensePlate}`
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((car) => (
                  <tr key={car.Id}>
                    <td>
                      <div className="table-car">
                        <CarImage car={car} />
                        <span>
                          <strong>{car.Name}</strong>
                          <small>{car.LicensePlate}</small>
                        </span>
                      </div>
                    </td>
                    <td>
                      {car.Seats} chỗ
                      <small>
                        {car.Brand} · {car.Year}
                      </small>
                    </td>
                    <td>
                      <strong>{money(car.DailyRate)}</strong>
                    </td>
                    <td>
                      <Badge status={car.Status} />
                    </td>
                    <td>
                      <div className="table-actions">
                        {isAdmin && (
                          <button
                            className="btn outline tiny"
                            onClick={() => setForm(car)}
                          >
                            <Settings2 size={14} />
                            Sửa
                          </button>
                        )}
                        <>
                          {isAdmin && (
                            <select
                              aria-label={`Đổi trạng thái ${car.Name}`}
                              value=""
                              disabled={busy === car.Id}
                              onChange={(e) =>
                                changeStatus(car, e.target.value)
                              }
                            >
                              <option value="">Đổi trạng thái</option>
                              {carStatuses
                                .filter((s) => s !== car.Status)
                                .map((s) => (
                                  <option value={s} key={s}>
                                    {statusLabel[s]}
                                  </option>
                                ))}
                            </select>
                          )}
                        </>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!cars.length && <Empty title="Đội xe chưa có xe" />}
        </div>
      )}
      {form && (
        <CarForm
          car={form === "new" ? null : form}
          onClose={() => setForm(null)}
          onDone={load}
        />
      )}
    </>
  );
}
function UserManagement() {
  const { user, notify } = useApp();
  const [users, setUsers] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [editing, setEditing] = useState(null),
    [busy, setBusy] = useState(false),
    [createOpen, setCreateOpen] = useState(false);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setUsers(asList(await api.get("/users")));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api.put(`/users/${editing.Id}`, {
        role: data.role,
        isActive: data.isActive === "true",
      });
      notify("Đã cập nhật quyền tài khoản.");
      setEditing(null);
      load();
    } catch (e) {
      notify(e.message, "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Người dùng & phân quyền</h2>
          <p>
            Khách hàng tự đặt xe. Nhân viên xử lý nghiệp vụ. Admin quản lý hệ
            thống.
          </p>
        </div>
        <button
          className="btn primary small"
          onClick={() => setCreateOpen(true)}
        >
          <Plus size={16} />
          Tạo tài khoản
        </button>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Người dùng</th>
                <th>Liên hệ</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.Id}>
                  <td>
                    <strong>{u.FullName}</strong>
                    <small>@{u.Username}</small>
                  </td>
                  <td>
                    {u.Email}
                    <small>{u.Phone}</small>
                  </td>
                  <td>
                    <span className="badge confirmed">{roleLabel[u.Role]}</span>
                  </td>
                  <td>
                    <span
                      className={`badge ${u.IsActive ? "available" : "suspended"}`}
                    >
                      {u.IsActive ? "Hoạt động" : "Đã khóa"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn outline tiny"
                      disabled={u.Id === user.id}
                      onClick={() => setEditing(u)}
                    >
                      Phân quyền
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {createOpen && (
        <CreateUser onClose={() => setCreateOpen(false)} onDone={load} />
      )}{" "}
      {editing && (
        <Modal
          title="Cập nhật quyền truy cập"
          subtitle={`${editing.FullName} · @${editing.Username}`}
          onClose={() => setEditing(null)}
        >
          <form className="modal-body form-stack" onSubmit={save}>
            <Field label="Vai trò">
              <select name="role" defaultValue={editing.Role}>
                {Object.entries(roleLabel).map(([r, label]) => (
                  <option value={r} key={r}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Trạng thái tài khoản">
              <select name="isActive" defaultValue={String(!!editing.IsActive)}>
                <option value="true">Hoạt động</option>
                <option value="false">Khóa tài khoản</option>
              </select>
            </Field>
            <Submit busy={busy}>Lưu quyền truy cập</Submit>
          </form>
        </Modal>
      )}
    </>
  );
}
function CreateUser({ onClose, onDone }) {
  const { notify } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post(
        "/users",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      notify("Đã tạo tài khoản mới.");
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
      title="Tạo tài khoản người dùng"
      subtitle="Cấp tài khoản cho nhân viên hoặc khách hàng."
      onClose={onClose}
    >
      <form onSubmit={submit} className="modal-body form-stack">
        <div className="form-grid">
          <Field label="Họ và tên">
            <input name="fullName" required maxLength={100} />
          </Field>
          <Field label="Tên đăng nhập">
            <input name="username" required minLength={3} maxLength={50} />
          </Field>
          <Field label="Email">
            <input name="email" type="email" required maxLength={255} />
          </Field>
          <Field label="Số điện thoại">
            <input
              name="phone"
              type="tel"
              required
              pattern="[0-9+() .-]{9,20}"
            />
          </Field>
        </div>
        <Field label="Mật khẩu khởi tạo">
          <input
            name="password"
            type="password"
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
          />
        </Field>
        <Field label="Vai trò">
          <select name="role" defaultValue="employee">
            {Object.entries(roleLabel).map(([role, label]) => (
              <option value={role} key={role}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {error && <ErrorBox message={error} />}
        <Submit busy={busy}>Tạo tài khoản</Submit>
      </form>
    </Modal>
  );
}
function AuditLogs() {
  const [logs, setLogs] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [selected, setSelected] = useState(null),
    [search, setSearch] = useState("");
  async function load() {
    setLoading(true);
    try {
      setLogs(asList(await api.get("/audit-logs")));
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Lịch sử thay đổi</h2>
          <p>Ai đã thay đổi điều gì và vào thời điểm nào.</p>
        </div>
        <button className="btn outline small" onClick={load}>
          <RefreshCw size={16} />
          Làm mới
        </button>
      </div>
      <div className="list-toolbar">
        <div className="input-icon">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm người, thao tác, đối tượng…"
          />
        </div>
        <span className="subtle">{logs.length} thao tác được ghi nhận</span>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : !logs.length ? (
        <Empty title="Chưa có lịch sử thao tác" />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Thời điểm</th>
                <th>Người thực hiện</th>
                <th>Thao tác</th>
                <th>Đối tượng</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {logs
                .filter((l) =>
                  `${l.Username || l.UserName || l.UserId} ${l.Action} ${l.EntityType} ${l.EntityId}`
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((l) => (
                  <tr key={l.Id}>
                    <td>{dateTime(l.CreatedAt)}</td>
                    <td>{l.Username || l.UserName || l.UserId}</td>
                    <td>
                      <code>{l.Action}</code>
                    </td>
                    <td>
                      {l.EntityType} #{l.EntityId}
                    </td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setSelected(l)}
                      >
                        Chi tiết
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {selected && (
        <Modal
          title="Chi tiết nhật ký"
          subtitle={`${selected.Action} · ${dateTime(selected.CreatedAt)}`}
          onClose={() => setSelected(null)}
          wide
        >
          <div className="modal-body">
            <div className="form-grid">
              <div>
                <h3>Dữ liệu trước</h3>
                <pre className="audit-json">
                  {pretty(
                    selected.OldValue || selected.OldValues || selected.OldData,
                  )}
                </pre>
              </div>
              <div>
                <h3>Dữ liệu sau</h3>
                <pre className="audit-json">
                  {pretty(
                    selected.NewValue || selected.NewValues || selected.NewData,
                  )}
                </pre>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
function pretty(data) {
  if (!data) return "Không có";
  try {
    return JSON.stringify(
      typeof data === "string" ? JSON.parse(data) : data,
      null,
      2,
    );
  } catch {
    return String(data);
  }
}
function Dashboard() {
  const { notify } = useApp();
  const [report, setReport] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [range, setRange] = useState({ start: "", end: "" });
  async function load() {
    setLoading(true);
    try {
      let query = "";
      if (range.start || range.end) {
        if (!range.start || !range.end)
          throw new Error("Vui lòng chọn đủ ngày bắt đầu và kết thúc.");
        const start = new Date(range.start + "T00:00:00"),
          end = new Date(range.end + "T23:59:59");
        if (end < start)
          throw new Error("Ngày kết thúc phải sau ngày bắt đầu.");
        query =
          "?" +
          new URLSearchParams({
            startDate: start.toISOString(),
            endDate: end.toISOString(),
          });
      }
      setReport(await api.get("/reports" + query));
      setError("");
    } catch (e) {
      if (report) notify(e.message, "error");
      else setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={load} />;
  const stats = [
    {
      title: "Tổng đơn thuê",
      value: report.totalOrders || 0,
      icon: ClipboardList,
      note: `${report.pendingOrders || 0} đơn chờ xác nhận`,
    },
    {
      title: "Xe đang được thuê",
      value: report.activeRentals || 0,
      icon: CarFront,
      note: `${report.totalCars || 0} xe trong đội xe`,
    },
    {
      title: "Doanh thu đã thu",
      value: money(report.totalRevenue),
      icon: Wallet,
      note: "Giao dịch thành công sau hoàn tiền",
    },
    {
      title: "Chuyến đi hoàn tất",
      value: report.completedOrders || 0,
      icon: CheckCircle2,
      note: "Đã trả xe và quyết toán",
    },
  ];
  const months = asList(report.revenueByMonth);
  const max = Math.max(1, ...months.map((m) => Number(m.revenue)));
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Tổng quan vận hành</h2>
          <p>Dữ liệu trực tiếp từ hệ thống thuê xe.</p>
        </div>
        <button className="btn outline small" onClick={load}>
          <RefreshCw size={16} />
          Làm mới
        </button>
      </div>
      <form
        className="report-filter"
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
      >
        <Field label="Từ ngày">
          <input
            type="date"
            value={range.start}
            onChange={(e) => setRange({ ...range, start: e.target.value })}
          />
        </Field>
        <Field label="Đến ngày">
          <input
            type="date"
            value={range.end}
            onChange={(e) => setRange({ ...range, end: e.target.value })}
          />
        </Field>
        <button className="btn outline small" type="submit">
          Xem báo cáo
        </button>
      </form>
      <div className="stats-grid">
        {stats.map((s) => (
          <div className="stat-card" key={s.title}>
            <div>
              <span>{s.title}</span>
              <s.icon size={21} />
            </div>
            <strong>{s.value}</strong>
            <small>{s.note}</small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <h3>Doanh thu theo tháng</h3>
          {months.length ? (
            <div className="bar-chart">
              {months.map((m, i) => (
                <div key={i}>
                  <strong>{money(m.revenue)}</strong>
                  <div className="bar-track">
                    <span
                      style={{
                        height: `${Math.max(3, (Number(m.revenue) / max) * 100)}%`,
                      }}
                    />
                  </div>
                  <small>{m.month}</small>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="Chưa có doanh thu"
              text="Giao dịch thành công sẽ được tổng hợp tại đây."
            />
          )}
        </section>
        <section className="panel">
          <h3>Công việc cần chú ý</h3>
          <div className="task-summary">
            <span>
              <ClockIcon />
              Đơn chờ xác nhận
            </span>
            <strong>{report.pendingOrders || 0}</strong>
          </div>
          <div className="task-summary">
            <span>
              <CarFront size={19} />
              Xe sẵn sàng
            </span>
            <strong>{report.availableCars || 0}</strong>
          </div>
          <div className="task-summary">
            <span>
              <Settings2 size={19} />
              Xe đang bảo trì
            </span>
            <strong>{report.maintenanceCars || 0}</strong>
          </div>
          <Link to="/orders" className="btn primary full">
            Đến danh sách đơn thuê
            <ArrowRight size={17} />
          </Link>
        </section>
      </div>
      <section className="panel utilization-panel">
        <h3>Hiệu suất khai thác theo xe</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Xe / Biển số</th>
                <th>Tổng đơn</th>
                <th>Hoàn tất</th>
                <th>Ngày thuê</th>
                <th>Tỷ lệ sử dụng</th>
                <th>Doanh thu</th>
              </tr>
            </thead>
            <tbody>
              {asList(report.vehicleUtilization).map((car) => (
                <tr key={car.carId}>
                  <td>
                    <strong>{car.carName}</strong>
                    <small>{car.licensePlate}</small>
                  </td>
                  <td>{car.totalOrders}</td>
                  <td>{car.completedOrders}</td>
                  <td>{Number(car.rentedDays || 0).toFixed(1)}</td>
                  <td>{Number(car.utilizationRate || 0).toFixed(1)}%</td>
                  <td>
                    <strong>{money(car.revenue)}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="info-note">
        <FileClock size={24} />
        <span>
          Quy trình chuẩn: tạo đơn → xác nhận → thanh toán cọc → nhận xe → trả
          xe → thanh toán còn lại → hoàn tất. Mọi thay đổi nghiệp vụ đều có nhật
          ký.
        </span>
      </div>
    </>
  );
}
function ClockIcon() {
  return <ClipboardList size={19} />;
}
export default function Management() {
  const { isAdmin } = useApp();
  const [tab, setTab] = useState("dashboard");
  const tabs = [
    ["dashboard", "Tổng quan", BarChart3],
    ["cars", "Đội xe", CarFront],
    ...(isAdmin
      ? [
          ["users", "Người dùng", Users],
          ["audit", "Nhật ký", FileClock],
        ]
      : []),
  ];
  return (
    <div className="container page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">LÁI VIỆT OPERATIONS</p>
          <h1>Bảng điều hành</h1>
          <p>Quản lý đội xe và vận hành những chuyến đi trọn vẹn.</p>
        </div>
        <span className="pill">
          <span className="live-dot" />
          Dữ liệu trực tiếp
        </span>
      </div>
      <div className="management-tabs">
        {tabs.map(([key, label, Icon]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </div>
      <div className="management-content">
        {tab === "dashboard" ? (
          <Dashboard />
        ) : tab === "cars" ? (
          <CarManagement />
        ) : tab === "users" ? (
          <UserManagement />
        ) : (
          <AuditLogs />
        )}
      </div>
    </div>
  );
}
