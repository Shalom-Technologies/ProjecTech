import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";
import ReviewForm from "../components/ReviewForm";
import { reviewsApi } from "../services/reviews";
import ReportProblemForm from "../components/ReportProblemForm";

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
  const [respondingId, setRespondingId] = useState(null);
  const [decisionNotes, setDecisionNotes] = useState({});
  const [deliveringId, setDeliveringId] = useState(null);
  const [reportingId, setReportingId] = useState(null);
  const [notice, setNotice] = useState("");

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

  const handlePriceDecision = async (project, approve) => {
    setRespondingId(project.id);
    setError("");
    try {
      await projectsApi.respondToPriceProposal(project.id, {
        approve,
        note: decisionNotes[project.id]?.trim() || null,
      });
      await loadProjects(activeTab);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        err.response?.data?.message ||
          (Array.isArray(detail) ? detail[0]?.msg : detail) ||
          "Could not send your response."
      );
      await loadProjects(activeTab);
    } finally {
      setRespondingId(null);
    }
  };

  const handleDeliver = async (project) => {
    if (
      !window.confirm(
        "Mark this project as delivered? The client then has 7 days to review it. If they do not object, the payment is released automatically."
      )
    ) {
      return;
    }
    setDeliveringId(project.id);
    setError("");
    setNotice("");
    try {
      await projectsApi.deliver(project.id);
      setNotice("Marked as delivered. The client has been asked to review the work.");
      await loadProjects(activeTab);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        err.response?.data?.message ||
          (Array.isArray(detail) ? detail[0]?.msg : detail) ||
          "Could not mark this project as delivered."
      );
    } finally {
      setDeliveringId(null);
    }
  };

  const handleReport = async (project, reason) => {
    await projectsApi.reportProblem(project.id, reason);
    setReportingId(null);
    setNotice("Your report was received. The payment will not be released until it has been reviewed.");
    await loadProjects(activeTab);
  };

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
      {notice && <div className="success-banner">{notice}</div>}

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
                  KES{(project.agreed_amount ?? project.budget).toLocaleString()} · Assigned{" "}
                  {new Date(project.assignment_date).toLocaleDateString()}
                </div>
              </Link>
              <span className={`status-badge status-${project.status}`}>
                {project.status.replace("_", " ")}
              </span>

              {project.dispute?.status === "open" && (
                <span className="status-badge status-disputed">Problem reported</span>
              )}
              {project.delivery?.status === "delivered" && project.status === "in_progress" && (
                <span className="status-badge status-delivered">
                  In client review until{" "}
                  {new Date(project.delivery.review_deadline).toLocaleDateString()}
                </span>
              )}

              <div className="project-row-actions">
              {project.status === "in_progress" &&
                project.is_funded &&
                project.delivery?.status !== "delivered" &&
                project.dispute?.status !== "open" && (
                  <button className="btn-primary" onClick={() => handleDeliver(project)} disabled={deliveringId === project.id}>
                    {deliveringId === project.id ? "Sending..." : "Mark as delivered"}
                  </button>
                )}

              {project.status === "in_progress" &&
                project.is_funded &&
                project.dispute?.status !== "open" && (
                  <button
                    className="btn-secondary"
                    onClick={() => setReportingId(reportingId === project.id ? null : project.id)}
                  >
                    Report a problem
                  </button>
                )}

              {project.status === "completed" && !reviewedMap[project.id] && (
                <button
                  className="btn-primary"
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
            </div>

            {project.status === "in_progress" &&
              project.price_proposal?.status === "pending" && (
                <div className="modal-note">
                  <p>
                    <strong>Price change requested:</strong> KES
                    {project.agreed_amount.toLocaleString()} → KES
                    {project.price_proposal.amount.toLocaleString()}
                  </p>
                  <p>Reason: {project.price_proposal.reason}</p>
                  <p>
                    Your earnings are calculated from this price, and the client cannot be
                    invoiced until you respond.
                  </p>
                  <div className="field">
                    <label htmlFor={`note-${project.id}`}>Note to the salesperson (optional)</label>
                    <input
                      id={`note-${project.id}`}
                      maxLength={500}
                      value={decisionNotes[project.id] || ""}
                      onChange={(e) =>
                        setDecisionNotes((prev) => ({ ...prev, [project.id]: e.target.value }))
                      }
                    />
                  </div>
                  <button
                    className="btn-primary"
                    onClick={() => handlePriceDecision(project, true)}
                    disabled={respondingId === project.id}
                  >
                    Approve new price
                  </button>{" "}
                  <button
                    className="btn-secondary"
                    onClick={() => handlePriceDecision(project, false)}
                    disabled={respondingId === project.id}
                  >
                    Decline
                  </button>
                </div>
              )}

            {project.status === "in_progress" && !project.is_funded && (
              <div className="modal-note">
                <p>Waiting for the client to pay. Start work once the project shows as funded.</p>
              </div>
            )}

            {project.dispute?.status === "open" && (
              <div className="modal-note">
                <p>
                  A problem was reported on this project. The payment is on hold until ProjecTech
                  has reviewed it.
                </p>
              </div>
            )}

            {reportingId === project.id && (
              <ReportProblemForm
                intro="Describe what is wrong. The payment will not be released until ProjecTech has reviewed it."
                onSubmit={(reason) => handleReport(project, reason)}
                onCancel={() => setReportingId(null)}
              />
            )}

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