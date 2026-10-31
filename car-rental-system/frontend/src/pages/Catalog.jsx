import React, { useState, useEffect, useMemo } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Fuel,
  Gauge,
  MapPin,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
  Users,
  Wallet,
  Wind,
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
  CarImage,
  Badge,
} from "../components/UI";
import {
  money,
  dateTime,
  defaultDates,
  validDates,
  localDate,
  transmissionLabel,
  fuelLabel,
} from "../utils";
import { useNavigate } from "react-router-dom";
function BookingModal({ car, dates, onClose }) {
  const { user, setAuthOpen, notify, reload } = useApp();
  const navigate = useNavigate();
  const [range, setRange] = useState(dates),
    [schedule, setSchedule] = useState([]),
    [quote, setQuote] = useState(null),
    [availability, setAvailability] = useState(null),
    [busy, setBusy] = useState(false),
    [checking, setChecking] = useState(false),
    [error, setError] = useState(""),
    [notes, setNotes] = useState("");
  useEffect(() => {
    api
      .get(`/cars/${car.Id}/schedule`)
      .then((data) => setSchedule(asList(data)))
      .catch(() => {});
  }, [car.Id]);
  useEffect(() => {
    setQuote(null);
    setAvailability(null);
    setError("");
  }, [range]);
  async function check() {
    const err = validDates(range.start, range.end);
    if (err) {
      setError(err);
      return;
    }
    setError("");
    setChecking(true);
    try {
      const body = {
        carId: car.Id,
        startDate: new Date(range.start).toISOString(),
        endDate: new Date(range.end).toISOString(),
      };
      const [q, a] = await Promise.all([
        api.post("/orders/quote", body),
        api.get(
          `/cars/${car.Id}/availability?${new URLSearchParams({ startDate: body.startDate, endDate: body.endDate })}`,
        ),
      ]);
      setQuote(q);
      setAvailability(a);
      if (!a.available)
        setError(
          "Xe đã có lịch hoặc không phục vụ trong khoảng thời gian này. Vui lòng chọn lịch khác.",
        );
    } catch (err) {
      setError(err.message);
    } finally {
      setChecking(false);
    }
  }
  async function book() {
    if (!user) {
      setAuthOpen(true);
      return;
    }
    if (!quote || !availability?.available) return;
    setBusy(true);
    setError("");
    try {
      await api.post("/orders", {
        carId: car.Id,
        startDate: new Date(range.start).toISOString(),
        endDate: new Date(range.end).toISOString(),
        notes,
      });
      notify("Đặt xe thành công! Đơn của bạn đang chờ xác nhận.");
      reload();
      onClose();
      navigate("/orders");
    } catch (err) {
      setError(err.message);
      setAvailability(null);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={car.Name}
      subtitle={`${car.Brand || ""} · ${car.Seats} chỗ · ${car.LicensePlate || ""}`}
      onClose={onClose}
      wide
    >
      <div className="booking-layout">
        <div className="car-detail">
          <div className="detail-image">
            <CarImage car={car} />
            <Badge status={car.Status} />
          </div>
          <div className="spec-grid">
            <span>
              <Users size={19} />
              {car.Seats} chỗ ngồi
            </span>
            <span>
              <Gauge size={19} />
              {transmissionLabel(car.Transmission)}
            </span>
            <span>
              <Fuel size={19} />
              {fuelLabel(car.FuelType)}
            </span>
            <span>
              <CalendarDays size={19} />
              {car.Year || "Đời mới"}
            </span>
          </div>
          <h3>Chiếc xe dành cho hành trình của bạn</h3>
          <p className="muted">
            {car.Description ||
              "Không gian thoải mái, vận hành êm ái. Sẵn sàng cùng bạn khám phá những cung đường mới."}
          </p>
          <div className="info-note">
            <ShieldCheck size={21} />
            <span>
              Giá và lịch được kiểm tra lại khi tạo đơn. Hai đơn thuê cùng xe
              không thể chồng lấn thời gian.
            </span>
          </div>
          <h3>Lịch đã đặt</h3>
          {schedule.length ? (
            <div className="schedule-list">
              {schedule.map((s, i) => (
                <div key={i}>
                  <CalendarDays size={16} />
                  <span>
                    {dateTime(s.StartDate)} → {dateTime(s.EndDate)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small-text">Chưa có lịch đặt đang hiệu lực.</p>
          )}
          <div className="policy-box">
            <h4>Chính sách rõ ràng, chuyến đi an tâm</h4>
            <p>
              1 ngày = 24 giờ, làm tròn lên. Đặt cọc {car.DepositRate ?? 30}%
              tiền thuê. Trả trễ: 150% giá ngày cho mỗi ngày trễ bắt đầu. Hủy
              sau xác nhận: 50% tiền cọc. Phí hư hỏng, nhiên liệu và vệ sinh
              được ghi rõ khi trả xe.
            </p>
          </div>
        </div>
        <div className="booking-panel">
          <p className="eyebrow">LÊN LỊCH HÀNH TRÌNH</p>
          <div className="detail-rate">
            {money(car.DailyRate)}
            <span>/ ngày</span>
          </div>
          <Field label="Nhận xe">
            <input
              type="datetime-local"
              value={range.start}
              min={localDate()}
              onChange={(e) => setRange({ ...range, start: e.target.value })}
              required
            />
          </Field>
          <Field label="Trả xe">
            <input
              type="datetime-local"
              value={range.end}
              min={range.start}
              onChange={(e) => setRange({ ...range, end: e.target.value })}
              required
            />
          </Field>
          <Submit busy={checking} onClick={check} className="btn outline full">
            <Search size={17} />
            Kiểm tra lịch & giá
          </Submit>
          {error && <ErrorBox message={error} />}{" "}
          {quote && availability?.available && (
            <>
              <div className="availability">
                <CheckCircle2 size={18} />
                Xe còn trống trong lịch bạn chọn
              </div>
              <div className="price-summary">
                <div>
                  <span>
                    {money(quote.dailyRate || car.DailyRate)} × {quote.days}{" "}
                    ngày
                  </span>
                  <strong>{money(quote.baseAmount)}</strong>
                </div>
                <div>
                  <span>Tiền cọc ({car.DepositRate ?? 30}%)</span>
                  <strong>{money(quote.depositAmount)}</strong>
                </div>
                <div className="price-total">
                  <span>Tổng tiền thuê</span>
                  <strong>{money(quote.totalAmount)}</strong>
                </div>
                <small>Tiền cọc được trừ vào tổng tiền thuê.</small>
              </div>
              <Field label="Ghi chú (không bắt buộc)">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  maxLength={1000}
                  placeholder="Điểm nhận xe, yêu cầu đặc biệt…"
                />
              </Field>
            </>
          )}
          <Submit
            busy={busy}
            onClick={book}
            className="btn primary full"
            disabled={!quote || !availability?.available}
          >
            {user ? "Xác nhận đặt xe" : "Đăng nhập để đặt xe"}
            <ArrowRight size={17} />
          </Submit>
          <p className="centered subtle">
            Không thu tiền thật. Thanh toán mô phỏng.
          </p>
        </div>
      </div>
    </Modal>
  );
}
export default function Catalog() {
  const [cars, setCars] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [brand, setBrand] = useState(""),
    [seats, setSeats] = useState(""),
    [maxPrice, setMaxPrice] = useState(""),
    [sort, setSort] = useState("recommended"),
    [dates, setDates] = useState(defaultDates),
    [appliedDates, setAppliedDates] = useState(null),
    [selected, setSelected] = useState(null),
    [filterOpen, setFilterOpen] = useState(false);
  const { refresh } = useApp();
  async function load() {
    setLoading(true);
    setError("");
    try {
      const qs = appliedDates
        ? `?${new URLSearchParams({ startDate: new Date(appliedDates.start).toISOString(), endDate: new Date(appliedDates.end).toISOString() })}`
        : "";
      setCars(asList(await api.get(`/cars${qs}`)));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, [refresh, appliedDates]);
  const brands = [...new Set(cars.map((c) => c.Brand).filter(Boolean))];
  const filtered = useMemo(() => {
    let out = cars.filter(
      (c) =>
        (!search ||
          `${c.Name} ${c.Brand} ${c.Model}`
            .toLowerCase()
            .includes(search.toLowerCase())) &&
        (!brand || c.Brand === brand) &&
        (!seats || Number(c.Seats) == Number(seats)) &&
        (!maxPrice || Number(c.DailyRate) <= Number(maxPrice)),
    );
    if (sort === "price-asc") out.sort((a, b) => a.DailyRate - b.DailyRate);
    if (sort === "price-desc") out.sort((a, b) => b.DailyRate - a.DailyRate);
    if (sort === "seats") out.sort((a, b) => b.Seats - a.Seats);
    return out;
  }, [cars, search, brand, seats, maxPrice, sort]);
  function find(e) {
    e.preventDefault();
    const err = validDates(dates.start, dates.end);
    if (err) {
      setError(err);
      return;
    }
    setAppliedDates({ ...dates });
    document
      .getElementById("cars")
      .scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return (
    <>
      <section className="hero">
        <div className="hero-grid-bg" />
        <div className="container hero-inner">
          <div className="hero-content">
            <p className="eyebrow">
              <span />
              TỰ DO TRÊN MỌI HÀNH TRÌNH
            </p>
            <h1>
              Đường dài phía trước.
              <br />
              <em>Chọn cách bạn đi.</em>
            </h1>
            <p>
              Chiếc xe phù hợp, lịch trình của riêng bạn.
              <br />
              Thuê xe dễ dàng để mỗi chuyến đi đều đáng nhớ.
            </p>
            <a href="#cars" className="btn primary">
              Khám phá đội xe <ArrowUpRight size={19} />
            </a>
            <div className="hero-proof">
              <span className="proof-icon">
                <ShieldCheck size={22} />
              </span>
              <span>
                Minh bạch chi phí <i>•</i> Chủ động hành trình
              </span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="hero-round-text">
              MAKE EVERY MILE A MEMORY • LÁI VIỆT •
            </div>
            <div className="landscape">
              <span className="sun" />
              <span className="hill hill-one" />
              <span className="hill hill-two" />
              <span className="road" />
            </div>
            <img src="/car.svg" alt="Xe du lịch trên hành trình Lái Việt" />
            <div className="hero-float">
              <span>
                <Check size={18} />
              </span>
              <div>
                Sẵn sàng lăn bánh<small>Xe tốt. Chuyến đi trọn vẹn.</small>
              </div>
            </div>
            <div className="hero-destination">
              <MapPin size={17} />
              <span>Đi bất cứ đâu bạn muốn</span>
              <ArrowUpRight size={17} />
            </div>
          </div>
        </div>
      </section>
      <div className="container search-position">
        <form className="search-panel" onSubmit={find}>
          <div className="search-title">
            <Search size={22} />
            <div>
              Tìm bạn đồng hành<small>Chọn thời gian cho chuyến đi</small>
            </div>
          </div>
          <label>
            <span>
              <CalendarDays size={15} />
              Ngày nhận xe
            </span>
            <input
              aria-label="Ngày nhận xe"
              type="datetime-local"
              required
              min={localDate()}
              value={dates.start}
              onChange={(e) => setDates({ ...dates, start: e.target.value })}
            />
          </label>
          <label>
            <span>
              <CalendarDays size={15} />
              Ngày trả xe
            </span>
            <input
              aria-label="Ngày trả xe"
              type="datetime-local"
              required
              min={dates.start}
              value={dates.end}
              onChange={(e) => setDates({ ...dates, end: e.target.value })}
            />
          </label>
          <button className="btn primary" type="submit">
            Tìm xe trống <ArrowRight size={18} />
          </button>
        </form>
      </div>
      <section id="cars" className="container catalog-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">MỖI CHUYẾN ĐI, MỘT LỰA CHỌN</p>
            <h2>
              Chọn xe. <span>Chạm tự do.</span>
            </h2>
            <p>
              Từ chuyến đi phố đến hành trình xa, luôn có một chiếc xe dành cho
              bạn.
            </p>
          </div>
          <span className="pill">
            <span className="live-dot" />
            {cars.length} chiếc xe trong đội ngũ
          </span>
        </div>
        <div className="catalog-layout">
          <aside className={`filters ${filterOpen ? "mobile-open" : ""}`}>
            <div className="filter-heading">
              <h3>
                <SlidersHorizontal size={17} />
                Bộ lọc tìm kiếm
              </h3>
              <button
                className="text-button"
                onClick={() => {
                  setSearch("");
                  setBrand("");
                  setSeats("");
                  setMaxPrice("");
                  setAppliedDates(null);
                }}
              >
                Đặt lại
              </button>
            </div>
            <Field label="Tìm theo tên xe">
              <div className="input-icon">
                <Search size={17} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="VD: Toyota, Xpander…"
                />
              </div>
            </Field>
            <Field label="Hãng xe">
              <select value={brand} onChange={(e) => setBrand(e.target.value)}>
                <option value="">Tất cả hãng xe</option>
                {brands.map((b) => (
                  <option key={b}>{b}</option>
                ))}
              </select>
            </Field>
            <Field label="Số chỗ ngồi">
              <select value={seats} onChange={(e) => setSeats(e.target.value)}>
                <option value="">Tất cả số chỗ</option>
                {[4, 5, 7, 9, 16, 29, 45].map((n) => (
                  <option value={n} key={n}>
                    {n} chỗ
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Giá tối đa / ngày (VNĐ)">
              <input
                type="number"
                min="0"
                step="100000"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                placeholder="Không giới hạn"
              />
            </Field>
            {appliedDates && (
              <div className="active-date">
                <CalendarDays size={18} />
                <div>
                  <strong>Đang lọc xe trống</strong>
                  <p>
                    {dateTime(appliedDates.start)}
                    <br />→ {dateTime(appliedDates.end)}
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setAppliedDates(null)}
                  >
                    Bỏ lọc thời gian
                  </button>
                </div>
              </div>
            )}
            <div className="filter-promise">
              <ShieldCheck size={27} />
              <h4>Đặt xe an tâm</h4>
              <p>
                Lịch trống chính xác.
                <br />
                Chi phí rõ ràng.
                <br />
                Hỗ trợ suốt quy trình thuê.
              </p>
              <span>
                ĐI ĐỂ CÓ THÊM CÂU CHUYỆN <ArrowUpRight size={17} />
              </span>
            </div>
          </aside>
          <div className="catalog-main">
            <div className="results-toolbar">
              <span>
                {loading ? (
                  "Đang tìm xe…"
                ) : (
                  <>
                    <strong>{filtered.length}</strong> xe phù hợp với bạn
                  </>
                )}
              </span>
              <div>
                <button
                  className="btn ghost small mobile-filter"
                  onClick={() => setFilterOpen(!filterOpen)}
                >
                  <SlidersHorizontal size={16} />
                  Lọc
                </button>
                <select
                  aria-label="Sắp xếp xe"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="recommended">Đề xuất cho bạn</option>
                  <option value="price-asc">Giá: thấp đến cao</option>
                  <option value="price-desc">Giá: cao đến thấp</option>
                  <option value="seats">Nhiều chỗ nhất</option>
                </select>
              </div>
            </div>
            {error && <ErrorBox message={error} onRetry={load} />}{" "}
            {loading ? (
              <Loading text="Đang chuẩn bị những chiếc xe tốt nhất…" />
            ) : !filtered.length ? (
              <Empty
                title="Chưa tìm thấy chiếc xe phù hợp"
                text="Thử đổi bộ lọc hoặc thời gian thuê cho hành trình của bạn."
                action={
                  <button
                    className="btn outline"
                    onClick={() => {
                      setSearch("");
                      setBrand("");
                      setSeats("");
                      setMaxPrice("");
                      setAppliedDates(null);
                    }}
                  >
                    Xóa bộ lọc
                  </button>
                }
              />
            ) : (
              <div className="car-grid">
                {filtered.map((car) => (
                  <article className="car-card" key={car.Id}>
                    <button
                      className="car-photo"
                      onClick={() => setSelected(car)}
                      aria-label={`Xem ${car.Name}`}
                    >
                      <CarImage car={car} />
                      <span className="car-tag">
                        {car.Seats > 5
                          ? "CHO CẢ GIA ĐÌNH"
                          : "KHÁM PHÁ MỖI NGÀY"}
                      </span>
                      <span
                        className={`car-status ${["maintenance", "suspended"].includes(car.Status) ? "unavailable" : ""}`}
                      >
                        <span />
                        {["maintenance", "suspended"].includes(car.Status)
                          ? "Tạm không phục vụ"
                          : "Kiểm tra lịch trống"}
                      </span>
                    </button>
                    <div className="car-card-body">
                      <div className="car-brand">
                        {car.Brand || "LÁI VIỆT"}
                        <span>{car.Year}</span>
                      </div>
                      <h3>
                        <button onClick={() => setSelected(car)}>
                          {car.Name}
                        </button>
                      </h3>
                      <div className="car-specs">
                        <span>
                          <Users size={15} />
                          {car.Seats} chỗ
                        </span>
                        <span>
                          <Gauge size={15} />
                          {transmissionLabel(car.Transmission)}
                        </span>
                        <span>
                          <Fuel size={15} />
                          {fuelLabel(car.FuelType)}
                        </span>
                      </div>
                      <div className="car-bottom">
                        <div>
                          <strong>{money(car.DailyRate)}</strong>
                          <span>/ ngày</span>
                        </div>
                        <button
                          className="car-book"
                          onClick={() => setSelected(car)}
                          disabled={["maintenance", "suspended"].includes(
                            car.Status,
                          )}
                          aria-label={`Chọn thuê ${car.Name}`}
                        >
                          <ArrowUpRight size={20} />
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div className="catalog-footnote">
              <ShieldCheck size={16} />
              Giá thuê chưa bao gồm phí phát sinh. Xem chi tiết trước khi đặt
              xe.
            </div>
          </div>
        </div>
      </section>
      <section id="how-it-works" className="how-section">
        <div className="container">
          <div className="section-title">
            <div>
              <p className="eyebrow">ĐƠN GIẢN TỪ ĐIỂM XUẤT PHÁT</p>
              <h2>
                Ít thủ tục hơn. <span>Nhiều trải nghiệm hơn.</span>
              </h2>
            </div>
          </div>
          <div className="steps-grid">
            {[
              {
                n: "01",
                icon: Search,
                title: "Chọn chiếc xe của bạn",
                text: "Tìm xe theo nhu cầu, chọn ngày nhận–trả và kiểm tra lịch trống.",
              },
              {
                n: "02",
                icon: Wallet,
                title: "Đặt xe & xác nhận",
                text: "Tạo đơn thuê, nhận xác nhận, xem hợp đồng và thanh toán cọc mô phỏng.",
              },
              {
                n: "03",
                icon: MapPin,
                title: "Nhận chìa khóa. Lên đường.",
                text: "Ghi nhận tình trạng khi nhận–trả xe, quyết toán minh bạch và hoàn tất.",
              },
            ].map((s) => (
              <div className="step" key={s.n}>
                <div className="step-top">
                  <span>{s.n}</span>
                  <s.icon size={24} />
                </div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
          <div className="journey-banner">
            <div>
              <Sparkles size={24} />
              <span>Chuyến đi tiếp theo của bạn bắt đầu từ đây.</span>
            </div>
            <a href="#cars">
              Tìm chiếc xe phù hợp <ArrowRight size={18} />
            </a>
          </div>
        </div>
      </section>
      {selected && (
        <BookingModal
          car={selected}
          dates={dates}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
