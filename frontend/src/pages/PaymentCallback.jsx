import { useState, useEffect, useRef } from "react";
import { useSearchParams, Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { paymentsApi } from "../services/payments";

export default function PaymentCallback() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("verifying"); // verifying | success | failed
  const [message, setMessage] = useState("");
  const hasVerified = useRef(false);

  useEffect(() => {
    if (hasVerified.current) return; // guard against double-invoke re-running verify twice
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
    <DashboardLayout>
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
            <p>Funds are now held securely until the project is marked complete.</p>
            <Link to="/dashboard/projects" className="btn-primary">
              Back to my projects
            </Link>
          </>
        )}

        {status === "failed" && (
          <>
            <div className="result-icon result-failed">×</div>
            <h2>Payment failed</h2>
            <p>{message}</p>
            <Link to="/dashboard/projects" className="btn-primary">
              Back to my projects
            </Link>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}