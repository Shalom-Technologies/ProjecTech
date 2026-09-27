export default function StarRating({ value }) {
  if (value == null) {
    return <span className="muted">No ratings yet</span>;
  }

  const fullStars = Math.round(value);

  return (
    <span className="star-display">
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= fullStars ? "star filled" : "star"}>
          ★
        </span>
      ))}
      <span className="star-value">{value.toFixed(1)}</span>
    </span>
  );
}