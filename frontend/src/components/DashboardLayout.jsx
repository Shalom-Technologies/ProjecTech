import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const SALESPERSON_NAV = [
  { label: "Overview", path: "/dashboard/overview" },
  { label: "My Projects", path: "/dashboard/projects" },
  { label: "Post a Project", path: "/dashboard/projects/new" },
  { label: "Messages", path: "/dashboard/messages" },
  { label: "Wallet", path: "/dashboard/wallet" },
  { label: "Transactions", path: "/dashboard/transactions" },
  { label: "Profile", path: "/dashboard/profile" },
  { label: "Settings", path: "/dashboard/settings" },
];

const DEVELOPER_NAV = [
  { label: "Browse Projects", path: "/dashboard/browse" },
  { label: "My Projects", path: "/dashboard/my-projects" },
  { label: "Messages", path: "/dashboard/messages" },
  { label: "Wallet", path: "/dashboard/wallet" },
  { label: "Transactions", path: "/dashboard/transactions" },
  { label: "Profile", path: "/dashboard/profile" },
  { label: "Settings", path: "/dashboard/settings" },
];

export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const navItems = user?.role === "developer" ? DEVELOPER_NAV : SALESPERSON_NAV;

  return (
    <div className="shell">
      <aside className="shell-sidebar">
        <div className="shell-brand">ProjecTech</div>

        <nav className="shell-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={location.pathname === item.path ? "active" : ""}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="shell-user">
          <div className="shell-user-name">
            {user?.first_name} {user?.last_name}
          </div>
          <div className="shell-user-role">{user?.role}</div>
          <button className="shell-logout" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>

      <main className="shell-main">{children}</main>
    </div>
  );
}