import { useState, useEffect, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import StarRating from "../components/StarRating";
import { useAuth } from "../context/AuthContext";
import { reviewsApi } from "../services/reviews";
import api from "../services/api";

export default function Profile() {
  const { user: cachedUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async () => {
    const res = await api.get("/api/users/profile");
    setProfile(res.data);
  }, []);

  const loadReviews = useCallback(async () => {
    if (!cachedUser) return;
    const res = await reviewsApi.getForUser(cachedUser.id, { per_page: 20 });
    setReviews(res.data.data);
  }, [cachedUser]);

  useEffect(() => {
    Promise.all([loadProfile(), loadReviews()]).finally(() => setLoading(false));
  }, [loadProfile, loadReviews]);

  if (!profile) return null;

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>My profile</h1>
      </div>

      <div className="profile-card">
        <div className="profile-avatar-large">
          {profile.first_name?.charAt(0)}
        </div>
        <div>
          <h2>
            {profile.first_name} {profile.last_name}
          </h2>
          <div className="profile-role">{profile.role}</div>
          <div className="profile-email">{profile.email}</div>
          <StarRating value={profile.average_rating} />
          <span className="muted"> ({profile.total_reviews} reviews)</span>
        </div>
      </div>

      <div className="profile-stats-row">
        <div className="stat-card">
          <div className="stat-value">{profile.completed_projects || 0}</div>
          <div className="stat-label">Completed projects</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">₦{(profile.total_earned || 0).toLocaleString()}</div>
          <div className="stat-label">Total earned</div>
        </div>
      </div>

      <section className="recent-section">
        <h2>Reviews received</h2>
        {loading && <p>Loading reviews...</p>}
        {!loading && reviews.length === 0 && (
          <p className="muted">No reviews yet.</p>
        )}
        <div className="reviews-list">
          {reviews.map((r) => (
            <div className="review-card" key={r.id}>
              <div className="review-header">
                <strong>{r.reviewer_name}</strong>
                <StarRating value={r.rating} />
              </div>
              <div className="review-project">{r.project_title}</div>
              <p>{r.comment}</p>
              <div className="review-date">
                {new Date(r.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      </section>
    </DashboardLayout>
  );
}