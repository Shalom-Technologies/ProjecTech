import api from "./api";

export const authApi = {
  changePassword: (data) => api.post("/api/auth/change-password", data),
  verifyEmail: (token) => api.post("/api/auth/verify-email", { token }),
  resendVerification: () => api.post("/api/auth/resend-verification"),
};