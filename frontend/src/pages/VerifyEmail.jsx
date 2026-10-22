import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { authApi } from "../services/auth";
import { useAuth } from "../context/AuthContext";

// The page the confirmation email links to. It confirms once when it opens.
export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const { user, refreshUser } = useAuth();
  const [state, setState] = useState(token ? "working" : "invalid");
  const [error, setError] = useState("");
  const started = useRef(false);

  // Keep confirmation links out of search engines.
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => document.head.removeChild(meta);
  }, []);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // React strict mode runs effects twice; the link works only once
    authApi
      .verifyEmail(token)
      .then(async () => {
        setState("done");
        if (localStorage.getItem("access_token")) await refreshUser();
      })
      .catch((err) => {
        setError(
          err.response?.data?.message ||
            err.response?.data?.detail ||
            "We couldn't confirm your email. Please try again."
        );
        setState("failed");
      });
  }, [token, refreshUser]);

  return (
    <div className="auth-page">
      <div className="auth-form">
        {state === "working" && <h1>Confirming your email...</h1>}

        {state === "done" && (
          <>
            <h1>Email confirmed</h1>
            <p>Thank you. You can now apply for projects, post projects, take payments and withdraw.</p>
            <p className="auth-links">
              <Link to={user ? "/dashboard" : "/login"}>{user ? "Go to my dashboard" : "Log in"}</Link>
            </p>
          </>
        )}

        {state === "failed" && (
          <>
            <h1>We couldn't confirm your email</h1>
            <p>{error}</p>
            <p>
              If you already confirmed it, you're all set. Otherwise log in and use "Send the
              email again" at the top of your dashboard.
            </p>
            <p className="auth-links">
              <Link to="/login">Log in</Link>
            </p>
          </>
        )}

        {state === "invalid" && (
          <>
            <h1>Invalid link</h1>
            <p>This confirmation link is missing or incomplete.</p>
            <p className="auth-links">
              <Link to="/login">Log in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
