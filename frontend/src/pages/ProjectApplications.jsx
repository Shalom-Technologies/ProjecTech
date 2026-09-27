import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";
import MessageButton from "../components/MessageButton";

export default function ProjectApplications() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actingOn, setActingOn] = useState(null);

  const loadApplications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await projectsApi.getApplications(id);
      setApplications(res.data.data);
    } catch {
      setError("Could not load applications for this project.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadApplications();
  }, [loadApplications]);

  const handleAccept = async (applicationId) => {
    if (!window.confirm("Assign this developer to the project?")) return;

    setActingOn(applicationId);
    try {
      await projectsApi.acceptApplication(id, applicationId);
      navigate("/dashboard/projects");
    } catch (err) {
      alert(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not accept this application."
      );
      setActingOn(null);
    }
  };

  const handleReject = async (applicationId) => {
    setActingOn(applicationId);
    try {
      await projectsApi.rejectApplication(id, applicationId);
      setApplications((prev) =>
        prev.map((a) =>
          a.application_id === applicationId ? { ...a, status: "rejected" } : a
        )
      );
    } catch (err) {
      alert(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not reject this application."
      );
    } finally {
      setActingOn(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Applications</h1>
      </div>

      {loading && <p>Loading applications...</p>}
      {error && <div className="form-error-banner">{error}</div>}

      {!loading && applications.length === 0 && (
        <div className="empty-state">
          <p>No developers have applied to this project yet.</p>
        </div>
      )}

      <div className="applications-list">
        {applications.map((app) => (
          <div className="application-card" key={app.application_id}>
            <div className="application-header">
              <div>
                <div className="application-name">{app.developer_name}</div>
                <div className="application-email">{app.developer_email}</div>
              </div>
              <span className={`status-badge status-${app.status}`}>
                {app.status}
              </span>
            </div>

            <p className="application-letter">{app.cover_letter}</p>

            <div className="application-footer">
              <span>Proposed budget: ₦{app.proposed_budget.toLocaleString()}</span>

              <div className="application-actions">
                <MessageButton
                  receiverId={app.developer_id}
                  projectId={id}
                  receiverName={app.developer_name}
                />

                {app.status === "pending" && (
                  <>
                    <button
                      className="btn-primary"
                      onClick={() => handleAccept(app.application_id)}
                      disabled={actingOn === app.application_id}
                    >
                      Accept & assign
                    </button>
                    <button
                      className="btn-danger"
                      onClick={() => handleReject(app.application_id)}
                      disabled={actingOn === app.application_id}
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}