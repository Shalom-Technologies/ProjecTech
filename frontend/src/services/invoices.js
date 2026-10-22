import api from "./api";

export const invoicesApi = {
  // Salesperson: the shareable link for a project
  getLinkForProject: (projectId) => api.post(`/api/invoices/for-project/${projectId}`),

  // Client (no login needed)
  view: (token) => api.get(`/api/invoices/${token}`),
  pay: (token) => api.post(`/api/invoices/${token}/pay`),
  accept: (token) => api.post(`/api/invoices/${token}/accept`),
  reportProblem: (token, reason) => api.post(`/api/invoices/${token}/dispute`, { reason }),
};
