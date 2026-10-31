import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { api, getToken } from "../services/api";
const Context = createContext(null);
export const useApp = () => useContext(Context);
export function AppProvider({ children }) {
  const [user, setUser] = useState(null),
    [authLoading, setAuthLoading] = useState(true),
    [authOpen, setAuthOpen] = useState(false),
    [toast, setToast] = useState(null),
    [refresh, setRefresh] = useState(0);
  const notify = useCallback(
    (message, type = "success") => setToast({ message, type, id: Date.now() }),
    [],
  );
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    let live = true;
    if (!getToken()) {
      setAuthLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((data) => {
        if (live) setUser(data.user || data);
      })
      .catch(() => localStorage.removeItem("lai-viet-token"))
      .finally(() => {
        if (live) setAuthLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);
  const login = async (credentials, register = false) => {
    let data = await api.post(
      register ? "/auth/register" : "/auth/login",
      credentials,
    );
    if (!data.token && register)
      data = await api.post("/auth/login", {
        username: credentials.username,
        password: credentials.password,
      });
    if (!data.token || !data.user)
      throw new Error("Máy chủ chưa tạo được phiên đăng nhập.");
    localStorage.setItem("lai-viet-token", data.token);
    setUser(data.user);
    setAuthOpen(false);
    setRefresh((v) => v + 1);
    notify(
      register
        ? "Đăng ký thành công. Chào mừng bạn đến Lái Việt!"
        : "Đăng nhập thành công.",
    );
    return data.user;
  };
  const logout = () => {
    localStorage.removeItem("lai-viet-token");
    setUser(null);
    setRefresh((v) => v + 1);
    notify("Bạn đã đăng xuất.");
  };
  return (
    <Context.Provider
      value={{
        user,
        setUser,
        authLoading,
        authOpen,
        setAuthOpen,
        login,
        logout,
        notify,
        refresh,
        reload: () => setRefresh((v) => v + 1),
        isStaff: ["employee", "admin"].includes(user?.role),
        isAdmin: user?.role === "admin",
      }}
    >
      {children}
      {toast && (
        <div className={`toast ${toast.type}`} role="status">
          <span>{toast.type === "error" ? "!" : "✓"}</span>
          {toast.message}
          <button onClick={() => setToast(null)} aria-label="Đóng thông báo">
            ×
          </button>
        </div>
      )}
    </Context.Provider>
  );
}
