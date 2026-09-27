import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../services/auth";
import api from "../services/api";

export default function Settings() {
  const { user } = useAuth();

  const [profileForm, setProfileForm] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    phone: user?.phone || "",
    bio: user?.bio || "",
    location: user?.location || "",
  });
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  const handleProfileChange = (e) => {
    setProfileForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setProfileError("");
    setProfileSuccess("");
    setSavingProfile(true);
    try {
      await api.put("/api/users/profile", profileForm);
      setProfileSuccess("Profile updated. Refresh to see changes reflected everywhere.");
    } catch (err) {
      setProfileError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not update profile."
      );
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordChange = (e) => {
    setPasswordForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError("New passwords do not match.");
      return;
    }

    setSavingPassword(true);
    try {
      await authApi.changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordSuccess("Password changed successfully.");
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err) {
      setPasswordError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not change password."
      );
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      <div className="settings-grid">
        <div className="settings-card">
          <h3>Profile information</h3>
          <form onSubmit={handleProfileSubmit}>
            {profileError && <div className="form-error-banner">{profileError}</div>}
            {profileSuccess && <div className="success-banner">{profileSuccess}</div>}

            <div className="field-row">
              <div className="field">
                <label htmlFor="first_name">First name</label>
                <input
                  id="first_name"
                  name="first_name"
                  value={profileForm.first_name}
                  onChange={handleProfileChange}
                />
              </div>
              <div className="field">
                <label htmlFor="last_name">Last name</label>
                <input
                  id="last_name"
                  name="last_name"
                  value={profileForm.last_name}
                  onChange={handleProfileChange}
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="phone">Phone</label>
              <input
                id="phone"
                name="phone"
                value={profileForm.phone}
                onChange={handleProfileChange}
              />
            </div>

            <div className="field">
              <label htmlFor="location">Location</label>
              <input
                id="location"
                name="location"
                value={profileForm.location}
                onChange={handleProfileChange}
              />
            </div>

            <div className="field">
              <label htmlFor="bio">Bio</label>
              <textarea
                id="bio"
                name="bio"
                rows={3}
                value={profileForm.bio}
                onChange={handleProfileChange}
              />
            </div>

            <button type="submit" disabled={savingProfile}>
              {savingProfile ? "Saving..." : "Save profile"}
            </button>
          </form>
        </div>

        <div className="settings-card">
          <h3>Change password</h3>
          <form onSubmit={handlePasswordSubmit}>
            {passwordError && <div className="form-error-banner">{passwordError}</div>}
            {passwordSuccess && <div className="success-banner">{passwordSuccess}</div>}

            <div className="field">
              <label htmlFor="current_password">Current password</label>
              <input
                id="current_password"
                name="current_password"
                type="password"
                value={passwordForm.current_password}
                onChange={handlePasswordChange}
              />
            </div>

            <div className="field">
              <label htmlFor="new_password">New password</label>
              <input
                id="new_password"
                name="new_password"
                type="password"
                value={passwordForm.new_password}
                onChange={handlePasswordChange}
              />
            </div>

            <div className="field">
              <label htmlFor="confirm_password">Confirm new password</label>
              <input
                id="confirm_password"
                name="confirm_password"
                type="password"
                value={passwordForm.confirm_password}
                onChange={handlePasswordChange}
              />
            </div>

            <button type="submit" disabled={savingPassword}>
              {savingPassword ? "Saving..." : "Change password"}
            </button>
          </form>
        </div>
      </div>
    </DashboardLayout>
  );
}