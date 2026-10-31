import React, { useState } from "react";
import { ShieldCheck, UserRound } from "lucide-react";
import { useApp } from "../context/AppContext";
import { api } from "../services/api";
import { Field, Submit, ErrorBox } from "../components/UI";
import { roleLabel } from "../utils";
export default function Profile() {
  const { user, setUser, notify } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.put(
        "/auth/profile",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      setUser(data.user || data);
      notify("Đã cập nhật thông tin tài khoản.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="container page narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">THÔNG TIN CÁ NHÂN</p>
          <h1>Tài khoản của tôi</h1>
          <p>Thông tin chính xác giúp chuyến đi thuận tiện hơn.</p>
        </div>
      </div>
      <div className="profile-layout">
        <aside>
          <div className="profile-avatar">
            {(user.fullName || user.username).charAt(0)}
          </div>
          <h2>{user.fullName}</h2>
          <p>@{user.username}</p>
          <span className="badge confirmed">{roleLabel[user.role]}</span>
          <div className="info-note">
            <ShieldCheck size={23} />
            <span>Vai trò và quyền truy cập do quản trị viên cấp.</span>
          </div>
        </aside>
        <form className="panel form-stack" onSubmit={submit}>
          <h2>Hồ sơ của bạn</h2>
          <Field label="Họ và tên">
            <input
              name="fullName"
              defaultValue={user.fullName}
              required
              maxLength={100}
            />
          </Field>
          <Field label="Email">
            <input
              name="email"
              type="email"
              defaultValue={user.email}
              required
              maxLength={255}
            />
          </Field>
          <Field label="Số điện thoại">
            <input
              name="phone"
              type="tel"
              defaultValue={user.phone}
              pattern="[0-9+() .-]{9,20}"
              maxLength={20}
            />
          </Field>
          <Field label="Địa chỉ">
            <textarea
              name="address"
              defaultValue={user.address}
              rows={3}
              maxLength={255}
            />
          </Field>
          {error && <ErrorBox message={error} />}
          <Submit busy={busy}>Lưu thông tin</Submit>
        </form>
      </div>
    </div>
  );
}
