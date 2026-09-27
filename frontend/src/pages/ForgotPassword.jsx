import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle"); // idle | sending | sent | error
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("sending");
    setError("");

    try {
      await api.post("/api/auth/forgot-password", { email });
      setStatus("sent");
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Something went wrong. Please try again."
      );
      setStatus("error");
    }
  };

  if (status === "sent") {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Check your email</h1>
          <p>
            If an account exists for <strong>{email}</strong>, we've sent a
            password reset link to it.
          </p>
          <p className="auth-links">
            <Link to="/login">Back to login</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Forgot password</h1>
        <p>Enter your email and we'll send you a reset link.</p>

        {error && <div className="auth-error">{error}</div>}

        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <button type="submit" disabled={status === "sending"}>
          {status === "sending" ? "Sending..." : "Send reset link"}
        </button>

        <p className="auth-links">
          <Link to="/login">Back to login</Link>
        </p>
      </form>
    </div>
  );
}