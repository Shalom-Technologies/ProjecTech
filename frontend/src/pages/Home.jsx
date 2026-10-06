import { Link } from "react-router-dom";
import PublicNav from "../components/PublicNav";

const STEPS = [
  {
    title: "A salesperson finds a need",
    text: "They talk to clients, spot what software someone needs, and post it as a project.",
  },
  {
    title: "A developer builds it",
    text: "Developers browse open projects, apply, and chat directly with the salesperson to agree the details.",
  },
  {
    title: "The client pays, safely",
    text: "Payment is held securely until the project is marked complete, then released to everyone involved.",
  },
];

export default function Home() {
  return (
    <div className="lp">
      <PublicNav />

      <section className="lp-hero">
        <div className="lp-hero-text">
          <h1>Turn client needs into shipped software.</h1>
          <p>
            ProjecTech connects salespeople who find clients with freelance
            developers who build what they need, with payments held securely
            until the work is done.
          </p>
          <div className="lp-hero-actions">
            <Link to="/register" className="lp-btn lp-btn-primary lp-btn-lg">
              Get started
            </Link>
            <Link to="/blog" className="lp-btn lp-btn-ghost lp-btn-lg">
              Read the blog
            </Link>
          </div>
        </div>

        <div className="lp-hero-card" aria-hidden="true">
          <span className="lp-example-tag">Example project</span>
          <div className="lp-hero-card-category">Web development</div>
          <h3>Online store for a local retailer</h3>
          <p>Product catalogue, cart and card payments for a small shop.</p>
          <div className="lp-hero-card-footer">
            <strong>₦450,000</strong>
            <span className="lp-pill">Open</span>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <h2>How it works</h2>
        <div className="lp-steps">
          {STEPS.map((step, i) => (
            <div className="lp-step" key={step.title}>
              <div className="lp-step-number">{i + 1}</div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-audiences">
          <div className="lp-audience">
            <h3>For salespeople</h3>
            <p>
              You already know what clients want. Post the project, pick the
              developer you trust, and earn a share of every sale without
              writing a line of code.
            </p>
            <Link to="/register">Sign up as a salesperson →</Link>
          </div>
          <div className="lp-audience">
            <h3>For developers</h3>
            <p>
              Skip the hunt for clients. Browse real, funded opportunities,
              focus on building, and get paid through the platform when the
              work is done.
            </p>
            <Link to="/register">Sign up as a developer →</Link>
          </div>
        </div>
      </section>

      <section className="lp-cta">
        <h2>Ready to get started?</h2>
        <p>Create a free account in a minute.</p>
        <Link to="/register" className="lp-btn lp-btn-primary lp-btn-lg">
          Create your account
        </Link>
      </section>

      <footer className="lp-footer">
        <span>© {new Date().getFullYear()} ProjecTech</span>
        <nav>
          <Link to="/blog">Blog</Link>
          <Link to="/login">Log in</Link>
          <Link to="/register">Sign up</Link>
        </nav>
      </footer>
    </div>
  );
}
