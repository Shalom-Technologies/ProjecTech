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
};