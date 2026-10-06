import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function PublicNav() {
  const { user } = useAuth();

  return (
    <header className="lp-nav">
      <Link to="/" className="lp-brand">
        ProjecTech
      </Link>

      <nav className="lp-nav-links">
        <Link to="/blog">Blog</Link>
        {user ? (
          <Link to="/dashboard" className="lp-btn lp-btn-primary">
            Go to dashboard
          </Link>
        ) : (
          <>
            <Link to="/login">Log in</Link>
            <Link to="/register" className="lp-btn lp-btn-primary">
              Sign up
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
