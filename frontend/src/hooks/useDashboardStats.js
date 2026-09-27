import { useState, useEffect } from "react";
import { projectsApi } from "../services/projects";

export function useDashboardStats() {
  const [stats, setStats] = useState({
    totalProjects: 0,
    openProjects: 0,
    inProgress: 0,
    completed: 0,
    totalApplications: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      try {
        const res = await projectsApi.list({ per_page: 100 });
        const projects = res.data.data;

        if (cancelled) return;

        setStats({
          totalProjects: projects.length,
          openProjects: projects.filter((p) => p.status === "open").length,
          inProgress: projects.filter((p) => p.status === "in_progress").length,
          completed: projects.filter((p) => p.status === "completed").length,
          totalApplications: projects.reduce(
            (sum, p) => sum + (p.applications_count || 0),
            0
          ),
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadStats();
    return () => {
      cancelled = true;
    };
  }, []);

  return { stats, loading };
}