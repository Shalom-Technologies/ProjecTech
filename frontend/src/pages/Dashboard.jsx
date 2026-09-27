import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user, logout } = useAuth();

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Welcome, {user?.first_name}</h1>
      <p>Role: {user?.role}</p>
      <button onClick={logout}>Log out</button>
    </div>
  );
}