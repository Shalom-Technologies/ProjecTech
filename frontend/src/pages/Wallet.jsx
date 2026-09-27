import { useState, useEffect, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { walletApi } from "../services/wallet";

export default function Wallet() {
  const [wallet, setWallet] = useState(null);
  const [showBankForm, setShowBankForm] = useState(false);
  const [accountNumber, setAccountNumber] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadWallet = useCallback(async () => {
    const res = await walletApi.getWallet();
    setWallet(res.data);
  }, []);

  useEffect(() => {
    loadWallet();
  }, [loadWallet]);

  const handleAddBank = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await walletApi.addBankAccount({ account_number: accountNumber, bank_code: bankCode });
      setSuccessMsg("Bank account added successfully.");
      setShowBankForm(false);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not add bank account."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");

    if (!withdrawAmount || Number(withdrawAmount) <= 0) {
      setError("Enter a valid withdrawal amount.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await walletApi.withdraw({ amount: Number(withdrawAmount) });
      setSuccessMsg(res.data.message);
      setWithdrawAmount("");
      loadWallet();
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Withdrawal failed."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!wallet) {
    return (
      <DashboardLayout>
        <p>Loading wallet...</p>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Wallet</h1>
      </div>

      <div className="wallet-summary">
        <div className="wallet-card">
          <div className="wallet-label">Available balance</div>
          <div className="wallet-value">₦{wallet.wallet_balance.toLocaleString()}</div>
        </div>
        <div className="wallet-card">
          <div className="wallet-label">Total earned</div>
          <div className="wallet-value">₦{wallet.total_earned.toLocaleString()}</div>
        </div>
      </div>

      {error && <div className="form-error-banner">{error}</div>}
      {successMsg && <div className="success-banner">{successMsg}</div>}

      <div className="wallet-actions">
        <div className="wallet-action-card">
          <h3>Withdraw funds</h3>
          <form onSubmit={handleWithdraw}>
            <div className="field">
              <label htmlFor="withdrawAmount">Amount (₦)</label>
              <input
                id="withdrawAmount"
                type="number"
                min="1"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
              />
            </div>
            <button type="submit" disabled={submitting}>
              {submitting ? "Processing..." : "Withdraw to bank"}
            </button>
          </form>
        </div>

        <div className="wallet-action-card">
          <h3>Bank account</h3>
          {!showBankForm ? (
            <button className="btn-secondary" onClick={() => setShowBankForm(true)}>
              Add / update bank account
            </button>
          ) : (
            <form onSubmit={handleAddBank}>
              <div className="field">
                <label htmlFor="accountNumber">Account number</label>
                <input
                  id="accountNumber"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  maxLength={10}
                />
              </div>
              <div className="field">
                <label htmlFor="bankCode">Bank code</label>
                <input
                  id="bankCode"
                  value={bankCode}
                  onChange={(e) => setBankCode(e.target.value)}
                  placeholder="e.g. 058 for GTBank"
                />
              </div>
              <button type="submit" disabled={submitting}>
                {submitting ? "Verifying..." : "Save bank account"}
              </button>
            </form>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}