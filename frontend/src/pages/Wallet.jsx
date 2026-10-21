import { useState, useEffect, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { walletApi } from "../services/wallet";

export default function Wallet() {
  const [wallet, setWallet] = useState(null);
  const [showBankForm, setShowBankForm] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState("");
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

  const handleAddPayout = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await walletApi.addPayoutAccount({ phone_number: phoneNumber });
      setSuccessMsg("M-Pesa number saved.");
      setShowBankForm(false);
      setPhoneNumber("");
      loadWallet();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        err.response?.data?.message ||
          (Array.isArray(detail) ? detail[0]?.msg : detail) ||
          "Could not save M-Pesa number."
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
          <div className="wallet-value">KES{wallet.wallet_balance.toLocaleString()}</div>
        </div>
        {wallet.pending_balance > 0 && (
          <div className="wallet-card">
            <div className="wallet-label">Pending (released, available soon)</div>
            <div className="wallet-value">KES{wallet.pending_balance.toLocaleString()}</div>
          </div>
        )}
        <div className="wallet-card">
          <div className="wallet-label">Total earned</div>
          <div className="wallet-value">KES{wallet.total_earned.toLocaleString()}</div>
        </div>
      </div>

      {error && <div className="form-error-banner">{error}</div>}
      {successMsg && <div className="success-banner">{successMsg}</div>}

      <div className="wallet-actions">
        <div className="wallet-action-card">
          <h3>Withdraw to M-Pesa</h3>
          <form onSubmit={handleWithdraw}>
            <div className="field">
              <label htmlFor="withdrawAmount">Amount (KES)</label>
              <input
                id="withdrawAmount"
                type="number"
                min="1"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
              />
            </div>
            <button type="submit" disabled={submitting}>
              {submitting ? "Processing..." : "Withdraw to M-Pesa"}
            </button>
          </form>
        </div>

        <div className="wallet-action-card">
          <h3>M-Pesa payout number</h3>
          {wallet.payout_account && (
            <p>
              {wallet.payout_account.account_name} · {wallet.payout_account.phone_number}
            </p>
          )}
          {!showBankForm ? (
            <button className="btn-secondary" onClick={() => setShowBankForm(true)}>
              {wallet.payout_account ? "Change M-Pesa number" : "Add M-Pesa number"}
            </button>
          ) : (
            <form onSubmit={handleAddPayout}>
              <div className="field">
                <label htmlFor="phoneNumber">M-Pesa phone number</label>
                <input
                  id="phoneNumber"
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="e.g. 0712345678"
                />
              </div>
              <button type="submit" disabled={submitting}>
                {submitting ? "Saving..." : "Save M-Pesa number"}
              </button>
            </form>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}