import api from "./api";

export const supportApi = {
  send: (data) => api.post("/api/support", data),
};
