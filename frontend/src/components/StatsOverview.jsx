import { useDashboardStats } from "../hooks/useDashboardStats";

export default function StatsOverview() {
  const { stats, loading } = useDashboardStats();

  const cards = [
    { label: "Open", value: stats.openProjects },
    { label: "In progress", value: stats.inProgress },
    { label: "Completed", value: stats.completed },
    { label: "Applications received", value: stats.totalApplications },
  ];

  return (
    <div className="stats-row">
      {cards.map((card) => (
        <div className="stat-card" key={card.label}>
          <div className="stat-value">{loading ? "—" : card.value}</div>
          <div className="stat-label">{card.label}</div>
        </div>
      ))}
    </div>
  );
}