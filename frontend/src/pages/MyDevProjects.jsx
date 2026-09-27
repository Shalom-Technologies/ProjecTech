import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";
import ReviewForm from "../components/ReviewForm";
import { reviewsApi } from "../services/reviews";

const TABS = [
  { key: "in_progress", label: "Active" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

export default function MyDevProjects() {
  const [activeTab, setActiveTab] = useState("in_progress");
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewedMap, setReviewedMap] = useState({});
  const [reviewingProjectId, setReviewingProjectId] = useState(null);

    const loadProjects = useCallback(async (status) => {
    setLoading(true);
    setError("");
    try {
      const res = await projectsApi.getMyAssigned({ status });
      setProjects(res.data.data);

      if (status === "completed") {
        const checks = await Promise.all(
          res.data.data.map((p) =>
            reviewsApi.checkReviewed(p.id).then((r) => [p.id, r.data.has_reviewed])
          )
        );
        setReviewedMap(Object.fromEntries(checks));
      }
    } catch {
      setError("Could not load your projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects(activeTab);
  }, [activeTab, loadProjects]);

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>My projects</h1>
      </div>

      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? "tab active" : "tab"}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <p>Loading...</p>}
      {error && <div className="form-error-banner">{error}</div>}

      {!loading && projects.length === 0 && (
        <div className="empty-state">
          <p>
            {activeTab === "in_progress" &&
              "You don't have any active projects right now."}
            {activeTab === "completed" && "No completed projects yet."}
            {activeTab === "cancelled" && "No cancelled projects."}
          </p>
          {activeTab === "in_progress" && (
            <Link to="/dashboard/browse">Browse open projects</Link>
          )}
        </div>
      )}

            <div className="project-table">
        {projects.map((project) => (
          <div key={project.id}>
            <div className="project-row">
              <Link to={`/dashboard/browse/${project.id}`} className="project-row-main">
                <div className="project-row-title">{project.title}</div>
                <div className="project-row-meta">
                  KES{project.budget.toLocaleString()} · Assigned{" "}
                  {new Date(project.assignment_date).toLocaleDateString()}
                </div>
              </Link>
              <span className={`status-badge status-${project.status}`}>
                {project.status.replace("_", " ")}
              </span>

              {project.status === "completed" && !reviewedMap[project.id] && (
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
            </div>

            {reviewingProjectId === project.id && (
              <ReviewForm
                projectId={project.id}
                reviewedUserId={project.salesperson_id}
                reviewedUserName={project.salesperson_name}
                onSubmitted={() => {
                  setReviewedMap((prev) => ({ ...prev, [project.id]: true }));
                  setReviewingProjectId(null);
                }}
              />
            )}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}