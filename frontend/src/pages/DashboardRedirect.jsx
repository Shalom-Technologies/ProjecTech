import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function DashboardRedirect() {
  const { user } = useAuth();

  if (user?.role === "developer") {
    return <Navigate to="/dashboard/browse" replace />;
  }
  return <Navigate to="/dashboard/overview" replace />;
}