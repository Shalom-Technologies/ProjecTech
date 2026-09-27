import api from "./api";

export const walletApi = {
  getWallet: () => api.get("/api/users/wallet"),
  getTransactions: (params) => api.get("/api/users/transactions", { params }),
  addBankAccount: (data) => api.post("/api/users/bank-account", data),
  withdraw: (data) => api.post("/api/users/wallet/withdraw", data),
};