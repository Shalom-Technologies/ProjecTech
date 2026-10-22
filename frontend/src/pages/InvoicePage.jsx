import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { invoicesApi } from "../services/invoices";
import ReportProblemForm from "../components/ReportProblemForm";

// Public page: the client opens this from the link the salesperson sent them.
// No login. It always shows the current price and sends them to a fresh,
// secure Paystack checkout when they press "Pay".
export default function InvoicePage() {
  const { token } = useParams();
  const [invoice, setInvoice] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState("");
  const [accepting, setAccepting] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [message, setMessage] = useState("");

  const reload = async () => {
    const res = await invoicesApi.view(token);
    setInvoice(res.data);
  };

  // Invoice links are private; keep them out of search engines.
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => document.head.removeChild(meta);
  }, []);

  useEffect(() => {
    let cancelled = false;
    invoicesApi
      .view(token)
      .then((res) => {
        if (!cancelled) setInvoice(res.data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.response?.status === 404) setNotFound(true);
        else setLoadError("We couldn't load this invoice. Please try again in a moment.");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const handlePay = async () => {
    setPayError("");
    setPaying(true);
    try {
      const res = await invoicesApi.pay(token);
      window.location.href = res.data.authorization_url;
    } catch (err) {
      setPayError(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          "We couldn't start the payment. Please try again."
      );
      setPaying(false);
    }
  };

  const handleAccept = async () => {
    if (!window.confirm("Accept this work? The payment will be released to the team.")) return;
    setPayError("");
    setAccepting(true);
    try {
      await invoicesApi.accept(token);
      setMessage("Thank you. The payment has been released.");
      await reload();
    } catch (err) {
      setPayError(err.response?.data?.detail || "We couldn't record that. Please try again.");
    } finally {
      setAccepting(false);
    }
  };

  const handleReport = async (reason) => {
    await invoicesApi.reportProblem(token, reason);
    setShowReport(false);
    setMessage("Your report was received. The payment will not be released until it has been reviewed.");
    await reload();
  };

  if (notFound) {
    return (
      <div className="public-payment-page">
        <div className="payment-result">
          <div className="result-icon result-failed">×</div>
          <h2>Invoice not found</h2>
          <p>This link isn't valid. Please check it with the person who sent it to you.</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="public-payment-page">
        <div className="payment-result">
          <h2>Something went wrong</h2>
          <p>{loadError}</p>
        </div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="public-payment-page">
        <div className="payment-result">
          <div className="spinner" />
          <h2>Loading invoice...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="public-payment-page">
      <div className="payment-result">
        <p>Invoice{invoice.from_name ? ` from ${invoice.from_name}` : ""}</p>
        <h2>{invoice.project_title}</h2>
        {invoice.client_name && <p>Prepared for {invoice.client_name}</p>}

        <h1>
          {invoice.currency} {invoice.amount.toLocaleString()}
        </h1>

        {invoice.status === "payable" && (
          <>
            {payError && <div className="form-error-banner">{payError}</div>}
            <button className="btn-primary" onClick={handlePay} disabled={paying}>
              {paying ? "Opening secure checkout..." : "Pay securely"}
            </button>
            <p className="modal-note">
              You'll be taken to Paystack to pay by M-Pesa or card. The money is held
              safely. It is only released to the team after you accept the finished work,
              or 7 days after it is delivered if you do not object.
            </p>
          </>
        )}

        {message && <div className="success-banner">{message}</div>}
        {payError && invoice.status !== "payable" && (
          <div className="form-error-banner">{payError}</div>
        )}

        {invoice.status === "paid" && (
          <>
            <div className="result-icon result-success">✓</div>
            <p>This invoice has been paid. Thank you!</p>
            <p className="modal-note">
              The money is held safely while the work is done. You will be able to review
              it here once it is delivered. Something wrong already?
            </p>
            {!showReport && (
              <button className="btn-secondary" onClick={() => setShowReport(true)}>
                Report a problem
              </button>
            )}
          </>
        )}

        {invoice.status === "in_review" && (
          <>
            <p>
              The work was delivered. Please review it by{" "}
              <strong>{new Date(invoice.review_deadline).toLocaleDateString()}</strong>.
            </p>
            <p className="modal-note">
              If it is as agreed, accept it to release the payment. If something is wrong,
              report a problem and the payment stays on hold until ProjecTech has looked into
              it. If you do nothing, the payment is released on that date.
            </p>
            {!showReport && (
              <>
                <button className="btn-primary" onClick={handleAccept} disabled={accepting}>
                  {accepting ? "Please wait..." : "Accept the work"}
                </button>{" "}
                <button className="btn-secondary" onClick={() => setShowReport(true)}>
                  Report a problem
                </button>
              </>
            )}
          </>
        )}

        {showReport && (invoice.status === "paid" || invoice.status === "in_review") && (
          <ReportProblemForm
            intro="Tell us what is wrong. We will not release the payment until we have looked into it."
            onSubmit={handleReport}
            onCancel={() => setShowReport(false)}
          />
        )}

        {invoice.status === "disputed" && (
          <p>
            A problem was reported and the payment is on hold. ProjecTech will review it and
            contact you.
          </p>
        )}

        {invoice.status === "completed" && (
          <>
            <div className="result-icon result-success">✓</div>
            <p>This project is complete and the payment has been released. Thank you!</p>
          </>
        )}

        {invoice.status === "refunded" && (
          <p>This payment was refunded. It can take a few days to reach your account.</p>
        )}

        {invoice.status === "awaiting_price_approval" && (
          <p>
            The price for this project is being confirmed. Please check back shortly, or
            contact the person who sent you this link.
          </p>
        )}

        {invoice.status === "unavailable" && (
          <p>This invoice can't be paid right now. Please contact the person who sent it.</p>
        )}
      </div>
    </div>
  );
}
