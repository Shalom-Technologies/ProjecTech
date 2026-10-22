import { useEffect } from "react";
import { Link } from "react-router-dom";

export default function NotFound() {
  // A wrong address should not be indexed as a real page.
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => document.head.removeChild(meta);
  }, []);

  return (
    <div className="public-payment-page">
      <div className="payment-result">
        <h2>Page not found</h2>
        <p>This address doesn't lead anywhere. It may have been mistyped or moved.</p>
        <Link to="/">Go to the home page</Link>
      </div>
    </div>
  );
}
