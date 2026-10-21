import { useState, useEffect, useCallback } from "react";
import { projectsApi } from "../services/projects";
import { invoicesApi } from "../services/invoices";

function errorMessage(err, fallback) {
  const detail = err.response?.data?.detail;
  return (
    err.response?.data?.message ||
    (Array.isArray(detail) ? detail[0]?.msg : detail) ||
    fallback
  );
}

export default function PaymentModal({ project, onClose }) {
  const [price, setPrice] = useState(null);
  const [loadingPrice, setLoadingPrice] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [paymentLink, setPaymentLink] = useState(null);
  const [copied, setCopied] = useState(false);

  const [showChangeForm, setShowChangeForm] = useState(false);
  const [newAmount, setNewAmount] = useState("");
  const [reason, setReason] = useState("");

  const loadPrice = useCallback(async () => {
    try {
      const res = await projectsApi.getPrice(project.id);
      setPrice(res.data);
    } catch (err) {
      setError(errorMessage(err, "Could not load the project price."));
    } finally {
      setLoadingPrice(false);
    }
  }, [project.id]);

  useEffect(() => {
    loadPrice();
  }, [loadPrice]);

  const proposal = price?.price_proposal;
  const awaitingApproval = proposal?.status === "pending";
  const wasDeclined = proposal?.status === "rejected";

  const handleGenerate = async () => {
    setError("");
    setSubmitting(true);
    try {
      // The invoice link is permanent for this project. The client always sees the
      // current agreed price, and a fresh checkout is created when they press "Pay".
      const res = await invoicesApi.getLinkForProject(project.id);
      setPaymentLink(res.data.invoice_url);
    } catch (err) {
      setError(errorMessage(err, "Could not get the client payment link."));
    } finally {
      setSubmitting(false);
    }
  };

  const handlePropose = async (e) => {
    e.preventDefault();
    setError("");

    if (!newAmount || Number(newAmount) <= 0) {
      setError("Enter the new price.");
      return;
    }
    if (reason.trim().length < 10) {
      setError("Give a short reason (at least 10 characters) so the developer understands the change.");
      return;
    }

    setSubmitting(true);
    try {
      await projectsApi.proposePrice(project.id, {
        amount: Number(newAmount),
        reason: reason.trim(),
      });
      setShowChangeForm(false);
      setNewAmount("");
      setReason("");
      await loadPrice();
    } catch (err) {
      setError(errorMessage(err, "Could not send the price change."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async () => {
    setError("");
    setSubmitting(true);
    try {
      await projectsApi.withdrawPriceProposal(project.id);
      await loadPrice();
    } catch (err) {
      setError(errorMessage(err, "Could not withdraw the price change."));
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
        {loadingPrice && <p>Loading price...</p>}

        {!loadingPrice && price && !paymentLink && (
          <>
            <p>
              Agreed price: <strong>KES{price.agreed_amount.toLocaleString()}</strong>
            </p>

            {awaitingApproval && (
              <div className="modal-note">
                <p>
                  Waiting for the developer to approve a price change to{" "}
                  <strong>KES{proposal.amount.toLocaleString()}</strong>.
                </p>
                <p>Reason: {proposal.reason}</p>
                <p>You can create the payment link as soon as they respond.</p>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleWithdraw}
                  disabled={submitting}
                >
                  Withdraw this request
                </button>
              </div>
            )}

            {wasDeclined && (
              <div className="modal-note">
                <p>
                  The developer declined a price of KES{proposal.amount.toLocaleString()}
                  {proposal.response_note ? `: "${proposal.response_note}"` : "."}
                </p>
                <p>The price stays at KES{price.agreed_amount.toLocaleString()}.</p>
              </div>
            )}

            {!awaitingApproval && (
              <>
                <p className="modal-note">
                  This gives you a link to send to your client ({project.client_email}).
                  They'll see the project and the agreed price, and pay securely. Funds are
                  held until the project is marked complete.
                </p>
                <button type="button" onClick={handleGenerate} disabled={submitting}>
                  {submitting ? "Getting link..." : "Get client payment link"}
                </button>
              </>
            )}

            {!awaitingApproval && !price.is_funded && (
              <div style={{ marginTop: "1rem" }}>
                {!showChangeForm ? (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setShowChangeForm(true)}
                  >
                    Request a different price
                  </button>
                ) : (
                  <form onSubmit={handlePropose}>
                    <p className="modal-note">
                      The developer must approve any change before you can invoice it.
                    </p>
                    <div className="field">
                      <label htmlFor="newAmount">New price (KES)</label>
                      <input
                        id="newAmount"
                        type="number"
                        min="1"
                        value={newAmount}
                        onChange={(e) => setNewAmount(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="reason">Reason for the change</label>
                      <textarea
                        id="reason"
                        rows={3}
                        maxLength={500}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    </div>
                    <button type="submit" disabled={submitting}>
                      {submitting ? "Sending..." : "Send to developer for approval"}
                    </button>{" "}
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setShowChangeForm(false)}
                    >
                      Cancel
                    </button>
                  </form>
                )}
              </div>
            )}
          </>
        )}

        {paymentLink && (
          <div className="payment-link-box">
            <p>Send this link to your client. It stays the same even if the price changes:</p>
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
