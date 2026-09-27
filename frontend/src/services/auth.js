import api from "./api";

export const authApi = {
  changePassword: (data) => api.post("/api/auth/change-password", data),
};