import { useEffect } from "react";
import { Link } from "react-router-dom";
import PublicNav from "./PublicNav";

// Shared frame for the Terms of Service and Privacy Policy.
export default function LegalPage({ title, updated, children }) {
  useEffect(() => {
    const previous = document.title;
    document.title = `${title} | ProjecTech`;
    return () => {
      document.title = previous;
    };
  }, [title]);

  return (
    <div className="lp">
      <PublicNav />
      <article className="blog-post legal-page">
        <h1>{title}</h1>
        <div className="blog-post-meta">Last updated {updated}</div>
        <div className="blog-post-body">{children}</div>
        <p className="legal-switch">
          <Link to="/terms">Terms of Service</Link> · <Link to="/privacy">Privacy Policy</Link>
        </p>
      </article>
    </div>
  );
}
