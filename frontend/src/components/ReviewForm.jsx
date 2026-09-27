import { useState } from "react";
import { reviewsApi } from "../services/reviews";

export default function ReviewForm({ projectId, reviewedUserId, reviewedUserName, onSubmitted }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (comment.trim().length < 10) {
      setError("Please write at least 10 characters.");
      return;
    }

    setSubmitting(true);
    try {
      await reviewsApi.create({
        project_id: projectId,
        reviewed_user_id: reviewedUserId,
        rating,
        comment: comment.trim(),
      });
      onSubmitted();
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not submit review."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="review-form" onSubmit={handleSubmit}>
      <h4>Leave a review for {reviewedUserName}</h4>

      {error && <div className="form-error-banner">{error}</div>}

      <div className="star-picker">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            type="button"
            key={n}
            className={n <= rating ? "star filled" : "star"}
            onClick={() => setRating(n)}
          >
            ★
          </button>
        ))}
      </div>

      <textarea
        rows={3}
        placeholder="How was your experience working together?"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />

      <button type="submit" disabled={submitting}>
        {submitting ? "Submitting..." : "Submit review"}
      </button>
    </form>
  );
}