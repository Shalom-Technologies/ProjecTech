import api from "./api";

export const paymentsApi = {
  initialize: (data) => api.post("/api/payments/initialize", data),
  verify: (data) => api.post("/api/payments/verify", data),
  getTransaction: (id) => api.get(`/api/payments/${id}`),
  releaseEscrow: (transactionId) => api.post(`/api/payments/${transactionId}/release`),
  getProjectStatus: (projectId) => api.get(`/api/payments/project/${projectId}/status`),
};