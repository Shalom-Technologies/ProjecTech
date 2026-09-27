import api from "./api";

export const messagesApi = {
  send: (data) => api.post("/api/messages", data),
  listConversations: () => api.get("/api/conversations"),
  getConversation: (id) => api.get(`/api/conversations/${id}`),
  getMessages: (conversationId, params) =>
    api.get(`/api/conversations/${conversationId}/messages`, { params }),
};