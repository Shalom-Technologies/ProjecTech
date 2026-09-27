import { useState } from "react";
import { paymentsApi } from "../services/payments";

export default function PaymentModal({ project, onClose }) {
  const [amount, setAmount] = useState(project.budget);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [paymentLink, setPaymentLink] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async (e) => {
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
      setPaymentLink(res.data.authorization_url);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not generate payment link."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(paymentLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

        {!paymentLink ? (
          <form onSubmit={handleGenerate}>
            <div className="field">
              <label htmlFor="amount">Amount to invoice (KES)</label>
              <input
                id="amount"
                type="number"
                min="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>

            <p className="modal-note">
              This creates a payment link for {project.client_email} to pay directly.
              Funds are held securely until the project is marked complete.
            </p>

            <button type="submit" disabled={submitting}>
              {submitting ? "Generating link..." : "Generate payment link"}
            </button>
          </form>
        ) : (
          <div className="payment-link-box">
            <p>Send this link to your client to complete payment:</p>
            <div className="link-display">
              <input readOnly value={paymentLink} onFocus={(e) => e.target.select()} />
              <button type="button" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <button type="button" className="btn-secondary" onClick={onClose}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}