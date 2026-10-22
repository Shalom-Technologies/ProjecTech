import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supportApi } from "../services/support";

const TOPICS = [
  { value: "payments", label: "Payments and refunds" },
  { value: "account", label: "My account" },
  { value: "project", label: "A project" },
  { value: "report", label: "Report a user or a problem" },
  { value: "other", label: "Something else" },
];

export default function Support() {
  const { user } = useAuth();
  const [form, setForm] = useState({
    name: "",
    email: "",
    topic: "payments",
    message: "",
    website: "", // hidden field: real visitors leave it empty
  });
  const [status, setStatus] = useState("idle"); // idle | sending | sent
  const [error, setError] = useState("");

  // Signed-in people do not have to type their details again.
  useEffect(() => {
    if (!user) return;
    setForm((prev) => ({
      ...prev,
      name: prev.name || `${user.first_name} ${user.last_name}`.trim(),
      email: prev.email || user.email,
    }));
  }, [user]);

  useEffect(() => {
    const previous = document.title;
    document.title = "Support | ProjecTech";
    return () => {
      document.title = previous;
    };
  }, []);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setStatus("sending");
    try {
      await supportApi.send(form);
      setStatus("sent");
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "We could not send your message. Please email privacy@projectech.dev instead."
      );
      setStatus("idle");
    }
  };

  if (status === "sent") {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Message sent</h1>
          <p>
            Thanks. We received your message and will reply to {form.email}. Check your spam
            folder if you do not hear from us.
          </p>
          <p className="auth-links">
            <Link to={user ? "/dashboard" : "/"}>{user ? "Back to your dashboard" : "Back to the home page"}</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Support</h1>
        <p>
          Tell us what you need and we will reply by email. For a payment problem, include the
          project name.
        </p>

        {error && <div className="auth-error">{error}</div>}

        <label htmlFor="name">Your name</label>
        <input id="name" name="name" value={form.name} onChange={handleChange} maxLength={100} required />

        <label htmlFor="email">Your email</label>
        <input id="email" name="email" type="email" value={form.email} onChange={handleChange} required />

        <label htmlFor="topic">What is it about?</label>
        <select id="topic" name="topic" value={form.topic} onChange={handleChange}>
          {TOPICS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>

        <label htmlFor="message">Message</label>
        <textarea
          id="message"
          name="message"
          rows={6}
          value={form.message}
          onChange={handleChange}
          minLength={10}
          maxLength={3000}
          required
        />
        <p className="field-hint">{form.message.length} / 3000</p>

        <div className="hp-field" aria-hidden="true">
          <label htmlFor="website">Leave this empty</label>
          <input
            id="website"
            name="website"
            tabIndex={-1}
            autoComplete="off"
            value={form.website}
            onChange={handleChange}
          />
        </div>

        <button type="submit" disabled={status === "sending"}>
          {status === "sending" ? "Sending..." : "Send message"}
        </button>

        <p className="auth-links">
          <Link to={user ? "/dashboard" : "/"}>{user ? "Back to your dashboard" : "Back to the home page"}</Link>
        </p>
      </form>
    </div>
  );
}
