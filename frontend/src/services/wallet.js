import api from "./api";

export const walletApi = {
  getWallet: () => api.get("/api/users/wallet"),
  getTransactions: (params) => api.get("/api/users/transactions", { params }),
  addPayoutAccount: (data) => api.post("/api/users/payout-account", data),
  withdraw: (data) => api.post("/api/users/wallet/withdraw", data),
};