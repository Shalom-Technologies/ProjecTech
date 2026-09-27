import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";

export default function EditProject() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    projectsApi
      .getById(id)
      .then((res) => {
        setForm({
          title: res.data.title,
          description: res.data.description,
          budget: res.data.budget,
          status: res.data.status,
        });
      })
      .catch(() => setError("Could not load this project."));
  }, [id]);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await projectsApi.update(id, {
        title: form.title,
        description: form.description,
        budget: Number(form.budget),
        status: form.status,
      });
      navigate("/dashboard/projects");
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not save changes."
      );
    } finally {
      setSaving(false);
    }
  };

  if (!form) {
    return (
      <DashboardLayout>
        <p>{error || "Loading..."}</p>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Edit project</h1>
      </div>

      <form className="project-form" onSubmit={handleSubmit}>
        {error && <div className="form-error-banner">{error}</div>}

        <div className="field">
          <label htmlFor="title">Title</label>
          <input id="title" name="title" value={form.title} onChange={handleChange} />
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
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="budget">Budget (KES)</label>
            <input
              id="budget"
              name="budget"
              type="number"
              value={form.budget}
              onChange={handleChange}
            />
          </div>

          <div className="field">
            <label htmlFor="status">Status</label>
            <select id="status" name="status" value={form.status} onChange={handleChange}>
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        <button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save changes"}
        </button>
      </form>
    </DashboardLayout>
  );
}