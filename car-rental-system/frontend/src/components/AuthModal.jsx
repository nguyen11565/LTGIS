import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Modal, Field, Submit, ErrorBox } from "./UI";
export default function AuthModal() {
  const { authOpen, setAuthOpen, login } = useApp();
  const navigate = useNavigate();
  const [register, setRegister] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  if (!authOpen) return null;
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      const person = await login(data, register);
      if (["employee", "admin"].includes(person.role)) navigate("/manage");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={register ? "Bắt đầu hành trình mới" : "Chào mừng bạn trở lại"}
      subtitle="Một tài khoản, mọi hành trình cùng Lái Việt."
      onClose={() => {
        setAuthOpen(false);
        setError("");
      }}
    >
      <div className="auth-body">
        <div className="auth-switch">
          <button
            className={!register ? "active" : ""}
            onClick={() => {
              setRegister(false);
              setError("");
            }}
          >
            Đăng nhập
          </button>
          <button
            className={register ? "active" : ""}
            onClick={() => {
              setRegister(true);
              setError("");
            }}
          >
            Đăng ký
          </button>
        </div>
        <form onSubmit={submit} className="form-stack">
          {register && (
            <Field label="Họ và tên">
              <input
                name="fullName"
                autoComplete="name"
                required
                maxLength={100}
                placeholder="Nguyễn Minh Anh"
              />
            </Field>
          )}
          <Field
            label={register ? "Tên đăng nhập" : "Tên đăng nhập hoặc email"}
          >
            <input
              name="username"
              autoComplete="username"
              required
              minLength={3}
              maxLength={register ? 50 : 100}
              placeholder={
                register ? "Chọn tên đăng nhập" : "Tên đăng nhập hoặc email"
              }
            />
          </Field>
          {register && (
            <div className="form-grid">
              <Field label="Email">
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={255}
                  placeholder="ban@email.com"
                />
              </Field>
              <Field label="Số điện thoại">
                <input
                  name="phone"
                  type="tel"
                  autoComplete="tel"
                  required
                  pattern="[0-9+() .-]{9,20}"
                  placeholder="090 123 4567"
                />
              </Field>
            </div>
          )}
          <Field
            label="Mật khẩu"
            hint={
              register
                ? "Tối thiểu 8 ký tự, nên dùng chữ hoa, chữ thường và số."
                : null
            }
          >
            <input
              name="password"
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              required
              minLength={register ? 8 : 1}
              maxLength={128}
              placeholder="••••••••"
            />
          </Field>
          {error && <ErrorBox message={error} />}
          <Submit busy={busy}>
            {register ? "Tạo tài khoản" : "Đăng nhập"}
            <ArrowRight size={18} />
          </Submit>
        </form>
        <p className="subtle centered">
          <ShieldCheck size={15} /> Thông tin của bạn được bảo vệ.
        </p>
      </div>
    </Modal>
  );
}
