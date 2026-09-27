import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { projectsApi } from "../services/projects";

const CATEGORIES = [
  { value: "", label: "All categories" },
  { value: "web_development", label: "Web development" },
  { value: "mobile_app", label: "Mobile app" },
  { value: "backend", label: "Backend" },
  { value: "frontend", label: "Frontend" },
  { value: "design", label: "Design" },
];

export default function BrowseProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filters, setFilters] = useState({
    search: "",
    category: "",
    min_budget: "",
    max_budget: "",
  });

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { status: "open", per_page: 50 };
      if (filters.search) params.search = filters.search;
      if (filters.category) params.category = filters.category;
      if (filters.min_budget) params.min_budget = filters.min_budget;
      if (filters.max_budget) params.max_budget = filters.max_budget;

      const res = await projectsApi.list(params);
      setProjects(res.data.data);
    } catch {
      setError("Could not load projects.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const timeout = setTimeout(loadProjects, 300); // debounce search typing
    return () => clearTimeout(timeout);
  }, [loadProjects]);

  const handleFilterChange = (e) => {
    setFilters((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Browse projects</h1>
        <p>Find an open project to apply for.</p>
      </div>

      <div className="filter-bar">
        <input
          name="search"
          placeholder="Search by title or description"
          value={filters.search}
          onChange={handleFilterChange}
          className="filter-search"
        />

        <select name="category" value={filters.category} onChange={handleFilterChange}>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>

        <input
          name="min_budget"
          type="number"
          placeholder="Min KES"
          value={filters.min_budget}
          onChange={handleFilterChange}
        />
        <input
          name="max_budget"
          type="number"
          placeholder="Max KES"
          value={filters.max_budget}
          onChange={handleFilterChange}
        />
      </div>

      {loading && <p>Loading projects...</p>}
      {error && <div className="form-error-banner">{error}</div>}

      {!loading && projects.length === 0 && (
        <div className="empty-state">
          <p>No open projects match your filters right now.</p>
        </div>
      )}

      <div className="project-grid">
        {projects.map((project) => (
          <Link
            to={`/dashboard/browse/${project.id}`}
            className="project-card"
            key={project.id}
          >
            <div className="project-card-category">
              {project.category.replace("_", " ")}
            </div>
            <h3>{project.title}</h3>
            <p className="project-card-desc">{project.description}</p>
            <div className="project-card-footer">
              <span className="project-card-budget">
                KES{project.budget.toLocaleString()}
              </span>
              <span className="project-card-apps">
                {project.applications_count} application
                {project.applications_count !== 1 ? "s" : ""}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </DashboardLayout>
  );
}