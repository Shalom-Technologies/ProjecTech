import { useState } from "react";

// Small form used by everyone who can report a problem on a paid project.
// onSubmit(reason) should return a promise; it throws or rejects on failure.
export default function ReportProblemForm({ onSubmit, onCancel, intro }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (reason.trim().length < 10) {
      setError("Please describe the problem in at least 10 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(reason.trim());
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        err.response?.data?.message ||
          (Array.isArray(detail) ? detail[0]?.msg : detail) ||
          "Could not send your report. Please try again."
      );
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="modal-note">
      {intro && <p>{intro}</p>}
      {error && <div className="form-error-banner">{error}</div>}
      <div className="field">
        <label htmlFor="problem-reason">What is the problem?</label>
        <textarea
          id="problem-reason"
          rows={4}
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>
      <button type="submit" className="btn-primary" disabled={submitting}>
        {submitting ? "Sending..." : "Send report"}
      </button>{" "}
      <button type="button" className="btn-secondary" onClick={onCancel} disabled={submitting}>
        Cancel
      </button>
    </form>
  );
}
