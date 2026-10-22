import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import PaymentModal from "../components/PaymentModal";
import { projectsApi } from "../services/projects";
import ReviewForm from "../components/ReviewForm";
import { reviewsApi } from "../services/reviews";
import { paymentsApi } from "../services/payments";
import ReportProblemForm from "../components/ReportProblemForm";

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
  const [paymentMap, setPaymentMap] = useState({});
  const [reportingId, setReportingId] = useState(null);
  const [notice, setNotice] = useState("");
  const [resendingId, setResendingId] = useState(null);
  const [reopeningId, setReopeningId] = useState(null);
  const [shareLink, setShareLink] = useState({});
  const navigate = useNavigate();

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const res = await projectsApi.list({ per_page: 50 });
      setProjects(res.data.data);

      // Check funding/escrow state for every project that could have a payment
      const needsPaymentCheck = res.data.data.filter(
        (p) => ["in_progress", "completed", "cancelled"].includes(p.status)
      );
      const paymentChecks = await Promise.all(
        needsPaymentCheck.map((p) =>
          paymentsApi.getProjectStatus(p.id).then((r) => [p.id, r.data])
        )
      );
      setPaymentMap(Object.fromEntries(paymentChecks));

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

  const handleReport = async (project, reason) => {
    await projectsApi.reportProblem(project.id, reason);
    setReportingId(null);
    setNotice("Your report was received. The payment will not be released until it has been reviewed.");
    await loadProjects();
  };

  const handleResendEmail = async (project) => {
    setResendingId(project.id);
    setError("");
    setNotice("");
    try {
      const res = await projectsApi.resendReviewEmail(project.id);
      setShareLink((prev) => ({ ...prev, [project.id]: res.data.invoice_url }));
      if (res.data.sent) setNotice(`We sent the review email to ${project.client_email || "the client"} again.`);
      else setError("The email still couldn't be sent. Copy the link below and send it to your client yourself.");
      await loadProjects();
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not resend the email."
      );
    } finally {
      setResendingId(null);
    }
  };

  const handleReopen = async (project) => {
    if (
      !window.confirm(
        "Reopen this project? It goes back on the market so developers can apply, and you can pick a new developer. The earlier developer is removed from it."
      )
    ) {
      return;
    }
    setReopeningId(project.id);
    setError("");
    setNotice("");
    try {
      await projectsApi.reopen(project.id);
      navigate(`/dashboard/projects/${project.id}/applications`);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not reopen this project."
      );
    } finally {
      setReopeningId(null);
    }
  };

  // What the money is doing, in words, for a paid project.
  const paymentBadge = (project) => {
    const pay = paymentMap[project.id];
    if (pay?.escrow_status === "refunded") return { text: "Refunded to client", cls: "cancelled" };
    if (!pay?.is_funded) return null;
    if (pay.dispute?.status === "open") return { text: "Problem reported", cls: "disputed" };
    if (pay.escrow_status === "released") return { text: "Payment released", cls: "funded" };
    if (pay.delivery?.status === "delivered") {
      return {
        text: `In client review until ${new Date(pay.delivery.review_deadline).toLocaleDateString()}`,
        cls: "delivered",
      };
    }
    return { text: "Funded", cls: "funded" };
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
      {notice && <div className="success-banner">{notice}</div>}

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

              {paymentBadge(project) && (
                <span className={`status-badge status-${paymentBadge(project).cls}`}>
                  {paymentBadge(project).text}
                </span>
              )}

              <div className="project-row-actions">
                {project.status === "in_progress" && !paymentMap[project.id]?.is_funded && (
                  <button className="btn-primary" onClick={() => setPayingProject(project)}>
                    Fund project
                  </button>
                )}
                {project.status === "cancelled" && (
                  <button className="btn-primary" onClick={() => handleReopen(project)} disabled={reopeningId === project.id}>
                    {reopeningId === project.id ? "Reopening..." : "Reopen project"}
                  </button>
                )}
                {project.status === "in_progress" &&
                  paymentMap[project.id]?.is_funded &&
                  paymentMap[project.id]?.escrow_status === "held" &&
                  paymentMap[project.id]?.dispute?.status !== "open" && (
                    <button
                      className="btn-secondary"
                      onClick={() => setReportingId(reportingId === project.id ? null : project.id)}
                    >
                      Report a problem
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

            {paymentMap[project.id]?.delivery?.status === "delivered" &&
              paymentMap[project.id]?.delivery?.client_email_sent === false && (
                <div className="modal-note">
                  <p>
                    <strong>The client may not have received the review email.</strong> Until they
                    open the link, the review period still runs and the payment is released on{" "}
                    {new Date(paymentMap[project.id].delivery.review_deadline).toLocaleDateString()}.
                  </p>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => handleResendEmail(project)}
                    disabled={resendingId === project.id}
                  >
                    {resendingId === project.id ? "Sending..." : "Send the email again"}
                  </button>
                  {shareLink[project.id] && (
                    <div className="link-display">
                      <input readOnly value={shareLink[project.id]} onFocus={(e) => e.target.select()} />
                    </div>
                  )}
                </div>
              )}

            {paymentMap[project.id]?.dispute?.status === "open" && (
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