import { useState } from "react";
import { paymentsApi } from "../services/payments";

export default function PaymentModal({ project, onClose }) {
  const [amount, setAmount] = useState(project.budget);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handlePay = async (e) => {
    e.preventDefault();
    setError("");

    if (!amount || Number(amount) <= 0) {
      setError("Enter a valid amount.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await paymentsApi.initialize({
        project_id: project.id,
        amount: Number(amount),
      });
      // Redirect to Paystack's hosted checkout page
      window.location.href = res.data.authorization_url;
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not start payment. Please try again."
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          ×
        </button>

        <h2>Fund project</h2>
        <p className="modal-subtitle">{project.title}</p>

        {error && <div className="form-error-banner">{error}</div>}

        <form onSubmit={handlePay}>
          <div className="field">
            <label htmlFor="amount">Amount to pay (₦)</label>
            <input
              id="amount"
              type="number"
              min="1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>

          <div className="payment-breakdown">
            <div>
              <span>Developer (45%)</span>
              <span>₦{(amount * 0.45).toLocaleString()}</span>
            </div>
            <div>
              <span>Your commission (35%)</span>
              <span>₦{(amount * 0.35).toLocaleString()}</span>
            </div>
            <div>
              <span>Platform fee (20%)</span>
              <span>₦{(amount * 0.2).toLocaleString()}</span>
            </div>
          </div>

          <p className="modal-note">
            Funds are held securely until the project is marked complete.
          </p>

          <button type="submit" disabled={submitting}>
            {submitting ? "Redirecting to Paystack..." : "Proceed to pay"}
          </button>
        </form>
      </div>
    </div>
  );
}