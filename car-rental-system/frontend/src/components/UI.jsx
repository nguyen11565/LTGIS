import React, { useEffect } from "react";
import { X, LoaderCircle, Inbox, AlertCircle } from "lucide-react";
import { statusLabel } from "../utils";
export function Modal({ title, subtitle, children, onClose, wide = false }) {
  useEffect(() => {
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const listener = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", listener);
    return () => {
      document.body.style.overflow = old;
      window.removeEventListener("keydown", listener);
    };
  }, [onClose]);
  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <header className="modal-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Đóng">
            <X size={22} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
export function Badge({ status, children }) {
  return (
    <span className={`badge ${status}`}>
      {children || statusLabel[status] || status}
    </span>
  );
}
export function Loading({ text = "Đang tải dữ liệu…" }) {
  return (
    <div className="loading">
      <LoaderCircle size={24} className="spin" />
      {text}
    </div>
  );
}
export function Empty({ title = "Chưa có dữ liệu", text, action }) {
  return (
    <div className="empty">
      <span>
        <Inbox size={30} />
      </span>
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}
export function ErrorBox({ message, onRetry }) {
  return (
    <div className="error-box">
      <AlertCircle size={20} />
      <div>
        {message}
        {onRetry && (
          <button className="text-button" onClick={onRetry}>
            Thử lại
          </button>
        )}
      </div>
    </div>
  );
}
export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Submit({
  busy,
  children,
  className = "btn primary",
  ...props
}) {
  return (
    <button {...props} className={className} disabled={busy || props.disabled}>
      {busy && <LoaderCircle className="spin" size={17} />} {children}
    </button>
  );
}
export function CarImage({ car, className = "" }) {
  return (
    <img
      className={className}
      src={car.ImageUrl || "/car.svg"}
      alt={car.Name || "Xe du lịch"}
      loading="lazy"
      onError={(e) => {
        e.currentTarget.onerror = null;
        e.currentTarget.src = "/car.svg";
      }}
    />
  );
}
