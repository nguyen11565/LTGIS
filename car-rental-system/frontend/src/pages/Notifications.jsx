import React, { useState, useEffect } from "react";
import { Bell, CheckCheck, CalendarClock, ArrowUpRight } from "lucide-react";
import { useApp } from "../context/AppContext";
import { api, asList } from "../services/api";
import { Loading, Empty, ErrorBox, Submit } from "../components/UI";
import { dateTime } from "../utils";
import { OrderDetail } from "./Orders";
export default function Notifications() {
  const { notify, isStaff, refresh } = useApp();
  const [items, setItems] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState(null);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(asList(await api.get("/notifications")));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, [refresh]);
  async function read(item) {
    try {
      if (!item.IsRead) {
        await api.put(`/notifications/${item.Id}/read`, {});
        setItems(
          items.map((n) => (n.Id === item.Id ? { ...n, IsRead: true } : n)),
        );
      }
      const orderId = item.OrderId || item.RelatedOrderId;
      if (orderId) setSelected(orderId);
    } catch (e) {
      notify(e.message, "error");
    }
  }
  async function all() {
    setBusy(true);
    try {
      await api.put("/notifications/read-all", {});
      setItems(items.map((n) => ({ ...n, IsRead: true })));
      notify("Đã đánh dấu tất cả thông báo là đã đọc.");
    } catch (e) {
      notify(e.message, "error");
    } finally {
      setBusy(false);
    }
  }
  async function reminders() {
    setBusy(true);
    try {
      const result = await api.post("/notifications/reminders", {});
      notify(
        `Đã xử lý nhắc nhận xe${result?.sent != null ? `: ${result.sent} thông báo` : "."}`,
      );
      load();
    } catch (e) {
      notify(e.message, "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="container page narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">LUÔN ĐỒNG HÀNH CÙNG BẠN</p>
          <h1>Thông báo</h1>
          <p>Những cập nhật mới nhất cho mỗi chuyến đi.</p>
        </div>
        <Submit
          busy={busy}
          className="btn outline small"
          onClick={all}
          disabled={!items.some((n) => !n.IsRead)}
        >
          <CheckCheck size={17} />
          Đọc tất cả
        </Submit>
      </div>
      {isStaff && (
        <div className="info-note reminder-note">
          <CalendarClock size={22} />
          <div>
            <strong>Nhắc khách sắp nhận xe</strong>
            <p>
              Gửi thông báo trong ứng dụng cho lịch nhận xe trong 24 giờ tới.
              Mỗi lịch chỉ gửi một lần.
            </p>
          </div>
          <Submit busy={busy} className="btn outline small" onClick={reminders}>
            Gửi nhắc lịch
          </Submit>
        </div>
      )}
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : !items.length ? (
        <Empty
          title="Mọi thứ đã được cập nhật"
          text="Thông báo về đơn thuê và thanh toán sẽ xuất hiện ở đây."
        />
      ) : (
        <div className="notification-list">
          {items.map((item) => (
            <button
              className={`notification ${item.IsRead ? "read" : "unread"}`}
              key={item.Id}
              onClick={() => read(item)}
            >
              <span className="notification-icon">
                <Bell size={20} />
              </span>
              <div>
                <h3>{item.Title || "Cập nhật hành trình"}</h3>
                <p>{item.Message || item.Content}</p>
                <small>{dateTime(item.CreatedAt)}</small>
              </div>
              {!item.IsRead && <span className="unread-dot" />}
            </button>
          ))}
        </div>
      )}
      {selected && (
        <OrderDetail id={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
