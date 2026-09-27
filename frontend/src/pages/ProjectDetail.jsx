import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { projectsApi } from "../services/projects";
import MessageButton from "../components/MessageButton";

export default function ProjectDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [error, setError] = useState("");
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [coverLetter, setCoverLetter] = useState("");
  const [proposedBudget, setProposedBudget] = useState("");
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [applySuccess, setApplySuccess] = useState(false);

  useEffect(() => {
    projectsApi
      .getById(id)
      .then((res) => setProject(res.data))
      .catch(() => setError("Could not load this project."));
  }, [id]);

  const handleApply = async (e) => {
    e.preventDefault();
    setApplyError("");

    if (coverLetter.trim().length < 10) {
      setApplyError("Cover letter must be at least 10 characters.");
      return;
    }

    setApplying(true);
    try {
      await projectsApi.apply(id, {
        cover_letter: coverLetter.trim(),
        proposed_budget: proposedBudget ? Number(proposedBudget) : undefined,
      });
      setApplySuccess(true);
      setShowApplyForm(false);
    } catch (err) {
      setApplyError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not submit your application."
      );
    } finally {
      setApplying(false);
    }
  };

  if (error) {
    return (
      <DashboardLayout>
        <div className="form-error-banner">{error}</div>
      </DashboardLayout>
    );
  }

  if (!project) {
    return (
      <DashboardLayout>
        <p>Loading...</p>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <Link to="/dashboard/browse" className="back-link">
        ← Back to browse
      </Link>

      <div className="detail-header">
        <div className="project-card-category">
          {project.category.replace("_", " ")}
        </div>
        <h1>{project.title}</h1>
        <div className="detail-meta">
          ₦{project.budget.toLocaleString()} · Posted by {project.salesperson_name} ·{" "}
          {project.applications_count} application
          {project.applications_count !== 1 ? "s" : ""}
        </div>
        <div className="detail-header">
          <div className="project-card-category">
            {project.category.replace("_", " ")}
          </div>
          <h1>{project.title}</h1>
          <div className="detail-meta">
            ₦{project.budget.toLocaleString()} · Posted by {project.salesperson_name} ·{" "}
            {project.applications_count} application
            {project.applications_count !== 1 ? "s" : ""}
          </div>

          {user?.role === "developer" && (
            <MessageButton
              receiverId={project.salesperson_id}
              projectId={project.id}
              receiverName={project.salesperson_name}
            />
          )}
        </div>
      </div>

      <div className="detail-body">
        <h3>Description</h3>
        <p>{project.description}</p>

        {project.tags?.length > 0 && (
          <div className="tag-list">
            {project.tags.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {user?.role === "developer" && project.status === "open" && (
        <div className="apply-section">
          {applySuccess && (
            <div className="success-banner">
              Application submitted. You'll be notified if you're selected.
            </div>
          )}

          {!applySuccess && !showApplyForm && (
            <button className="btn-primary" onClick={() => setShowApplyForm(true)}>
              Apply for this project
            </button>
          )}

          {showApplyForm && (
            <form className="project-form" onSubmit={handleApply}>
              {applyError && <div className="form-error-banner">{applyError}</div>}

              <div className="field">
                <label htmlFor="coverLetter">Cover letter</label>
                <textarea
                  id="coverLetter"
                  rows={5}
                  value={coverLetter}
                  onChange={(e) => setCoverLetter(e.target.value)}
                  placeholder="Explain why you're a good fit for this project..."
                />
              </div>

              <div className="field">
                <label htmlFor="proposedBudget">
                  Proposed budget (₦, optional — defaults to listed budget)
                </label>
                <input
                  id="proposedBudget"
                  type="number"
                  value={proposedBudget}
                  onChange={(e) => setProposedBudget(e.target.value)}
                />
              </div>

              <button type="submit" disabled={applying}>
                {applying ? "Submitting..." : "Submit application"}
              </button>
            </form>
          )}
        </div>
      )}

      {project.status !== "open" && (
        <div className="empty-state">
          <p>This project is no longer accepting applications.</p>
        </div>
      )}
    </DashboardLayout>
  );
}