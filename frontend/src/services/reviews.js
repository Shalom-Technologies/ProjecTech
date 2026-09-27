import api from "./api";

export const reviewsApi = {
  create: (data) => api.post("/api/reviews", data),
  getForUser: (userId, params) => api.get(`/api/reviews/user/${userId}`, { params }),
  checkReviewed: (projectId) => api.get(`/api/reviews/check/${projectId}`),
};