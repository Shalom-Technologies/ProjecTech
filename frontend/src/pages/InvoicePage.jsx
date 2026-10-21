import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { invoicesApi } from "../services/invoices";

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
            <button onClick={handlePay} disabled={paying}>
              {paying ? "Opening secure checkout..." : "Pay securely"}
            </button>
            <p className="modal-note">
              You'll be taken to Paystack to pay by M-Pesa or card. The money is held
              safely and only released to the developer once the project is complete.
            </p>
          </>
        )}

        {invoice.status === "paid" && (
          <>
            <div className="result-icon result-success">✓</div>
            <p>This invoice has been paid. Thank you!</p>
          </>
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
