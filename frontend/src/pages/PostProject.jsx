import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";

const CATEGORIES = [
  "web_development",
  "mobile_app",
  "backend",
  "frontend",
  "design",
];

const initialForm = {
  title: "",
  description: "",
  category: "web_development",
  budget: "",
  currency: "NGN",
  deadline: "",
  client_name: "",
  client_email: "",
  tags: "",
};

function validate(form) {
  const errors = {};

  if (form.title.trim().length < 10) {
    errors.title = "Title must be at least 10 characters";
  }
  if (form.description.trim().length < 30) {
    errors.description = "Description must be at least 30 characters";
  }
  if (!form.budget || Number(form.budget) <= 0) {
    errors.budget = "Enter a budget greater than 0";
  }
  if (!form.deadline) {
    errors.deadline = "Deadline is required";
  } else if (new Date(form.deadline) <= new Date()) {
    errors.deadline = "Deadline must be in the future";
  }
  if (!form.client_name.trim()) {
    errors.client_name = "Client name is required";
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.client_email)) {
    errors.client_email = "Enter a valid client email";
  }

  return errors;
}

export default function PostProject() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError("");

    const validationErrors = validate(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setSubmitting(true);
    try {
      await projectsApi.create({
        title: form.title.trim(),
        description: form.description.trim(),
        detailed_requirements: form.description.trim(),
        category: form.category,
        budget: Number(form.budget),
        currency: form.currency,
        duration_estimate: "Not specified",
        deadline: new Date(form.deadline).toISOString(),
        client_name: form.client_name.trim(),
        client_email: form.client_email.trim(),
        tags: form.tags
          ? form.tags.split(",").map((t) => t.trim()).filter(Boolean)
          : [],
      });
      navigate("/dashboard/projects");
    } catch (err) {
      setSubmitError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not post project. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Post a new project</h1>
        <p>Describe the client's need so a developer can pick it up.</p>
      </div>

      <form className="project-form" onSubmit={handleSubmit} noValidate>
        {submitError && <div className="form-error-banner">{submitError}</div>}

        <div className="field">
          <label htmlFor="title">Project title</label>
          <input
            id="title"
            name="title"
            value={form.title}
            onChange={handleChange}
          />
          {errors.title && <span className="field-error">{errors.title}</span>}
        </div>

        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            rows={5}
            value={form.description}
            onChange={handleChange}
          />
          {errors.description && (
            <span className="field-error">{errors.description}</span>
          )}
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="category">Category</label>
            <select
              id="category"
              name="category"
              value={form.category}
              onChange={handleChange}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="budget">Budget (KES)</label>
            <input
              id="budget"
              name="budget"
              type="number"
              min="1"
              value={form.budget}
              onChange={handleChange}
            />
            {errors.budget && (
              <span className="field-error">{errors.budget}</span>
            )}
          </div>
        </div>

        <div className="field">
          <label htmlFor="deadline">Deadline</label>
          <input
            id="deadline"
            name="deadline"
            type="date"
            value={form.deadline}
            onChange={handleChange}
          />
          {errors.deadline && (
            <span className="field-error">{errors.deadline}</span>
          )}
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="client_name">Client name</label>
            <input
              id="client_name"
              name="client_name"
              value={form.client_name}
              onChange={handleChange}
            />
            {errors.client_name && (
              <span className="field-error">{errors.client_name}</span>
            )}
          </div>

          <div className="field">
            <label htmlFor="client_email">Client email</label>
            <input
              id="client_email"
              name="client_email"
              type="email"
              value={form.client_email}
              onChange={handleChange}
            />
            {errors.client_email && (
              <span className="field-error">{errors.client_email}</span>
            )}
          </div>
        </div>

        <div className="field">
          <label htmlFor="tags">Tags (comma-separated, optional)</label>
          <input
            id="tags"
            name="tags"
            placeholder="react, nodejs, ecommerce"
            value={form.tags}
            onChange={handleChange}
          />
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? "Posting..." : "Post project"}
        </button>
      </form>
    </DashboardLayout>
  );
}