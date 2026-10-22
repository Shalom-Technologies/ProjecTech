import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    role: "developer",
    accepted_terms: false,
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, type, value, checked } = e.target;
    setFormData({ ...formData, [name]: type === "checkbox" ? checked : value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await register(formData);
      navigate("/dashboard");
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Registration failed. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Create an account</h1>

        {error && <div className="auth-error">{error}</div>}

        <label>I am a...</label>
        <div className="role-toggle">
          <button
            type="button"
            className={formData.role === "developer" ? "active" : ""}
            onClick={() => setFormData({ ...formData, role: "developer" })}
          >
            Developer
          </button>
          <button
            type="button"
            className={formData.role === "salesperson" ? "active" : ""}
            onClick={() => setFormData({ ...formData, role: "salesperson" })}
          >
            Salesperson
          </button>
        </div>

        <div className="name-row">
          <div>
            <label htmlFor="first_name">First name</label>
            <input
              id="first_name"
              name="first_name"
              value={formData.first_name}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="last_name">Last name</label>
            <input
              id="last_name"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              required
            />
          </div>
        </div>

        <label htmlFor="email">Email</label>
        <input
          id="email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          required
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          minLength={8}
          required
        />
        <p className="field-hint">
          At least 8 characters, with uppercase, lowercase, and a number.
        </p>

        <label className="terms-check" htmlFor="accepted_terms">
          <input
            id="accepted_terms"
            name="accepted_terms"
            type="checkbox"
            checked={formData.accepted_terms}
            onChange={handleChange}
            required
          />
          <span>
            I am 18 or older and I agree to the{" "}
            <Link to="/terms" target="_blank" rel="noopener noreferrer">Terms of Service</Link> and the{" "}
            <Link to="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</Link>.
          </span>
        </label>

        <button type="submit" disabled={submitting}>
          {submitting ? "Creating account..." : "Sign up"}
        </button>

        <p className="auth-links">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}