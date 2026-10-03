import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import PaymentModal from "../components/PaymentModal";
import { projectsApi } from "../services/projects";
import ReviewForm from "../components/ReviewForm";
import { reviewsApi } from "../services/reviews";
import { paymentsApi } from "../services/payments";

const STATUS_LABELS = {
  open: "Open",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

export default function MyProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const [payingProject, setPayingProject] = useState(null);
  const [reviewedMap, setReviewedMap] = useState({});
  const [reviewingProjectId, setReviewingProjectId] = useState(null);
  const [fundedMap, setFundedMap] = useState({});
  const navigate = useNavigate();

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const res = await projectsApi.list({ per_page: 50 });
      setProjects(res.data.data);

           const inProgress = res.data.data.filter((p) => p.status === "in_progress");
      console.log("inProgress projects:", inProgress);

      const fundedChecks = await Promise.all(
        inProgress.map((p) =>
          paymentsApi.getProjectStatus(p.id).then((r) => {
            console.log(`Funding check for ${p.id}:`, r.data);
            return [p.id, r.data.is_funded];
          })
        )
      );
      console.log("fundedChecks array:", fundedChecks);

      setFundedMap(Object.fromEntries(fundedChecks));

      const completed = res.data.data.filter((p) => p.status === "completed");
      const reviewChecks = await Promise.all(
        completed.map((p) => reviewsApi.checkReviewed(p.id).then((r) => [p.id, r.data.has_reviewed]))
      );
      setReviewedMap(Object.fromEntries(reviewChecks));
    } catch {
      setError("Could not load your projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this project? This cannot be undone.")) return;

    setDeletingId(id);
    try {
      await projectsApi.delete(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      alert(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not delete this project."
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>My projects</h1>
        <Link to="/dashboard/projects/new" className="btn-primary">
          Post a project
        </Link>
      </div>

      {loading && <p>Loading projects...</p>}
      {error && <div className="form-error-banner">{error}</div>}

      {!loading && projects.length === 0 && (
        <div className="empty-state">
          <p>You haven't posted any projects yet.</p>
          <Link to="/dashboard/projects/new">Post your first project</Link>
        </div>
      )}

      <div className="project-table">
        {projects.map((project) => (
          <div key={project.id}>
            <div className="project-row">
              <div className="project-row-main">
                <div className="project-row-title">{project.title}</div>
                <div className="project-row-meta">
                  KES{project.budget.toLocaleString()} · {project.applications_count} application
                  {project.applications_count !== 1 ? "s" : ""}
                </div>
              </div>

              <span className={`status-badge status-${project.status}`}>
                {STATUS_LABELS[project.status] || project.status}
              </span>

              {project.status === "in_progress" && fundedMap[project.id] && (
                <span className="status-badge status-funded">Funded</span>
              )}

              <div className="project-row-actions">
                {project.status === "in_progress" && !fundedMap[project.id] && (
                  <button onClick={() => setPayingProject(project)}>
                    Fund project
                  </button>
                )}
                {project.status === "completed" &&
                  project.assigned_to &&
                  !reviewedMap[project.id] && (
                    <button
                      onClick={() =>
                        setReviewingProjectId(
                          reviewingProjectId === project.id ? null : project.id
                        )
                      }
                    >
                      Leave a review
                    </button>
                  )}
                <button onClick={() => navigate(`/dashboard/projects/${project.id}/applications`)}>
                  Applications
                </button>
                <button onClick={() => navigate(`/dashboard/projects/${project.id}/edit`)}>
                  Edit
                </button>
                <button
                  className="btn-danger"
                  onClick={() => handleDelete(project.id)}
                  disabled={deletingId === project.id}
                >
                  {deletingId === project.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>

            {reviewingProjectId === project.id && (
              <ReviewForm
                projectId={project.id}
                reviewedUserId={project.assigned_to}
                reviewedUserName={project.assigned_to_name}
                onSubmitted={() => {
                  setReviewedMap((prev) => ({ ...prev, [project.id]: true }));
                  setReviewingProjectId(null);
                }}
              />
            )}
          </div>
        ))}
      </div>

      {payingProject && (
        <PaymentModal
          project={payingProject}
          onClose={() => setPayingProject(null)}
        />
      )}
    </DashboardLayout>
  );
}