import React, { useState } from "react";
import {
  Routes,
  Route,
  NavLink,
  Link,
  Navigate,
  useLocation,
} from "react-router-dom";
import {
  ArrowUpRight,
  Bell,
  CarFront,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu,
  UserRound,
  X,
  Leaf,
  ArrowRight,
} from "lucide-react";
import { useApp } from "./context/AppContext";
import AuthModal from "./components/AuthModal";
import { Loading } from "./components/UI";
import Catalog from "./pages/Catalog";
import Orders from "./pages/Orders";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";
import Management from "./pages/Management";
function Protected({ children, staff = false, admin = false }) {
  const { user, authLoading, setAuthOpen, isStaff, isAdmin } = useApp();
  if (authLoading) return <Loading />;
  if (!user)
    return (
      <div className="container page">
        <div className="empty">
          <UserRound size={36} />
          <h2>Hành trình của riêng bạn</h2>
          <p>Đăng nhập để đặt xe và quản lý đơn thuê.</p>
          <button className="btn primary" onClick={() => setAuthOpen(true)}>
            Đăng nhập <ArrowRight size={17} />
          </button>
        </div>
      </div>
    );
  if ((staff && !isStaff) || (admin && !isAdmin))
    return <Navigate to="/" replace />;
  return children;
}
export default function App() {
  const { user, isStaff, setAuthOpen, logout } = useApp();
  const [menu, setMenu] = useState(false),
    [account, setAccount] = useState(false);
  const location = useLocation();
  React.useEffect(() => {
    setMenu(false);
    setAccount(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <>
      <div className="topbar">
        <span>Thêm một chuyến đi. Thêm một câu chuyện.</span>
        <span>
          <span className="live-dot" /> Đặt xe trực tuyến 24/7
        </span>
      </div>
      <header className="site-header">
        <div className="container header-inner">
          <Link to="/" className="brand">
            <span className="brand-icon">
              <CarFront size={27} />
            </span>
            <span>
              LÁI<span className="brand-dot">•</span>VIỆT
              <small>YOUR JOURNEY, YOUR WAY</small>
            </span>
          </Link>
          <nav className={menu ? "nav open" : "nav"}>
            <NavLink to="/" end>
              Khám phá xe
            </NavLink>
            <NavLink to="/orders">
              {isStaff ? "Đơn thuê xe" : "Chuyến đi của tôi"}
            </NavLink>
            {isStaff && <NavLink to="/manage">Điều hành</NavLink>}
            <a href="/#how-it-works" onClick={() => setMenu(false)}>
              Cách thuê xe
            </a>
          </nav>
          <div className="header-actions">
            {user ? (
              <>
                <Link
                  className="icon-button"
                  to="/notifications"
                  title="Thông báo"
                  aria-label="Thông báo"
                >
                  <Bell size={21} />
                </Link>
                <div className="account-wrapper">
                  <button
                    className="account-button"
                    onClick={() => setAccount(!account)}
                  >
                    <span className="avatar">
                      {(user.fullName || user.username || "U").charAt(0)}
                    </span>
                    <span className="account-name">
                      {user.fullName || user.username}
                    </span>
                    <ChevronDown size={15} />
                  </button>
                  {account && (
                    <div className="account-dropdown">
                      <Link to="/profile">
                        <UserRound size={16} />
                        Tài khoản của tôi
                      </Link>
                      {isStaff && (
                        <Link to="/manage">
                          <LayoutDashboard size={16} />
                          Bảng điều hành
                        </Link>
                      )}
                      <button
                        onClick={() => {
                          logout();
                          setAccount(false);
                        }}
                      >
                        <LogOut size={16} />
                        Đăng xuất
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <button
                className="btn primary small"
                onClick={() => setAuthOpen(true)}
              >
                Đăng nhập <ArrowUpRight size={16} />
              </button>
            )}
            <button
              className="icon-button menu-button"
              aria-label="Mở menu"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route
            path="/orders"
            element={
              <Protected>
                <Orders />
              </Protected>
            }
          />
          <Route
            path="/notifications"
            element={
              <Protected>
                <Notifications />
              </Protected>
            }
          />
          <Route
            path="/profile"
            element={
              <Protected>
                <Profile />
              </Protected>
            }
          />
          <Route
            path="/manage"
            element={
              <Protected staff>
                <Management />
              </Protected>
            }
          />
          <Route
            path="*"
            element={
              <div className="container page">
                <h1>Trang này chưa có trên bản đồ.</h1>
                <Link className="btn primary" to="/">
                  Trở về khám phá xe
                </Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="site-footer">
        <div className="container footer-top">
          <div>
            <Link to="/" className="brand">
              <span className="brand-icon">
                <CarFront size={27} />
              </span>
              <span>
                LÁI<span className="brand-dot">•</span>VIỆT
                <small>YOUR JOURNEY, YOUR WAY</small>
              </span>
            </Link>
            <p>Tự do khám phá. An tâm trên mọi nẻo đường.</p>
          </div>
          <div className="footer-note">
            <Leaf size={22} />
            <span>
              Đi xa hơn, trải nghiệm nhiều hơn.
              <br />
              <strong>Một hành trình đẹp bắt đầu từ sự an tâm.</strong>
            </span>
          </div>
        </div>
        <div className="container footer-bottom">
          <span>
            © {new Date().getFullYear()} Lái Việt. Hệ thống quản lý và đặt thuê
            xe du lịch trực tuyến.
          </span>
          <span>Thanh toán mô phỏng • Không thu tiền thật</span>
        </div>
      </footer>
      <AuthModal />
    </>
  );
}
