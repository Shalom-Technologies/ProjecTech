import { Link } from "react-router-dom";
import { useEffect, useState, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import StatsOverview from "../components/StatsOverview";
import { projectsApi } from "../services/projects";

export default function DashboardHome() {
  const [recentProjects, setRecentProjects] = useState([]);

  const loadRecent = useCallback(async () => {
    const res = await projectsApi.list({ per_page: 5 });
    setRecentProjects(res.data.data);
  }, []);

  useEffect(() => {
    loadRecent();
  }, [loadRecent]);

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Overview</h1>
        <Link to="/dashboard/projects/new" className="btn-primary">
          Post a project
        </Link>
      </div>

      <StatsOverview />

      <section className="recent-section">
        <h2>Recent projects</h2>
        {recentProjects.length === 0 && (
          <p className="muted">Nothing posted yet.</p>
        )}
        <div className="project-table">
          {recentProjects.map((p) => (
            <div className="project-row" key={p.id}>
              <div className="project-row-main">
                <div className="project-row-title">{p.title}</div>
                <div className="project-row-meta">
                  KES{p.budget.toLocaleString()} · {p.applications_count} applications
                </div>
              </div>
              <span className={`status-badge status-${p.status}`}>{p.status}</span>
            </div>
          ))}
        </div>
        <Link to="/dashboard/projects" className="view-all-link">
          View all projects →
        </Link>
      </section>
    </DashboardLayout>
  );
}