import api from "./api";

export const projectsApi = {
  create: (data) => api.post("/api/projects", data),
  list: (params) => api.get("/api/projects", { params }),
  getById: (id) => api.get(`/api/projects/${id}`),
  update: (id, data) => api.put(`/api/projects/${id}`, data),
  delete: (id) => api.delete(`/api/projects/${id}`),
  apply: (id, data) => api.post(`/api/projects/${id}/apply`, data),
  getMyAssigned: (params) => api.get("/api/projects/mine/assigned", { params }),
  getApplications: (id) => api.get(`/api/projects/${id}/applications`),
  acceptApplication: (projectId, applicationId) =>
    api.post(`/api/projects/${projectId}/applications/${applicationId}/accept`),
  rejectApplication: (projectId, applicationId) =>
    api.post(`/api/projects/${projectId}/applications/${applicationId}/reject`),

  // Delivery and problem reports
  deliver: (id) => api.post(`/api/projects/${id}/deliver`),
  reopen: (id) => api.post(`/api/projects/${id}/reopen`),
  resendReviewEmail: (id) => api.post(`/api/projects/${id}/resend-review-email`),
  reportProblem: (id, reason) => api.post(`/api/projects/${id}/dispute`, { reason }),

  // Agreed price and price-change proposals
  getPrice: (id) => api.get(`/api/projects/${id}/price`),
  proposePrice: (id, data) => api.post(`/api/projects/${id}/price-proposal`, data),
  withdrawPriceProposal: (id) => api.delete(`/api/projects/${id}/price-proposal`),
  respondToPriceProposal: (id, data) =>
    api.post(`/api/projects/${id}/price-proposal/respond`, data),
};