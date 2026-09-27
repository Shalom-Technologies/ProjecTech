import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { paymentsApi } from "../services/payments";

export default function PaymentVerify() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("verifying");
  const [message, setMessage] = useState("");
  const hasVerified = useRef(false);

  useEffect(() => {
    if (hasVerified.current) return;
    hasVerified.current = true;

    const reference = searchParams.get("reference") || searchParams.get("trxref");

    if (!reference) {
      setStatus("failed");
      setMessage("No payment reference found.");
      return;
    }

    paymentsApi
      .verify({ reference })
      .then((res) => {
        setStatus("success");
        setMessage(res.data.message);
      })
      .catch((err) => {
        setStatus("failed");
        setMessage(
          err.response?.data?.message ||
            err.response?.data?.detail ||
            "Payment could not be verified."
        );
      });
  }, [searchParams]);

  return (
    <div className="public-payment-page">
      <div className="payment-result">
        {status === "verifying" && (
          <>
            <div className="spinner" />
            <h2>Verifying your payment...</h2>
            <p>Please don't close this page.</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="result-icon result-success">✓</div>
            <h2>Payment successful</h2>
            <p>{message}</p>
            <p>Thank you! The project team has been notified.</p>
          </>
        )}

        {status === "failed" && (
          <>
            <div className="result-icon result-failed">×</div>
            <h2>Payment failed</h2>
            <p>{message}</p>
            <p>Please contact the person who sent you this link.</p>
          </>
        )}
      </div>
    </div>
  );
}