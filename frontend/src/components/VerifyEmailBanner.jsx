import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../services/auth";

// Shown on every dashboard page until the person confirms their email address.
export default function VerifyEmailBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  if (!user || user.email_verified) return null;

  const handleResend = async () => {
    setError("");
    setMessage("");
    setSending(true);
    try {
      const res = await authApi.resendVerification();
      setMessage(res.data.message);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "We couldn't send the email. Please try again."
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="modal-note" role="status">
      <p>
        <strong>Confirm your email address.</strong> Until you do, you can browse but you can't
        apply for projects, post projects, take payments or withdraw. We sent a link to{" "}
        {user.email}.
      </p>
      {message && <p>{message}</p>}
      {error && <p className="form-error-banner">{error}</p>}
      <button type="button" className="btn-secondary" onClick={handleResend} disabled={sending}>
        {sending ? "Sending..." : "Send the email again"}
      </button>
    </div>
  );
}
