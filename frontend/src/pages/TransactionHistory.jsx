import { useState, useEffect, useCallback } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { walletApi } from "../services/wallet";

export default function TransactionHistory() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const loadTransactions = useCallback(async (pageNum) => {
    setLoading(true);
    const res = await walletApi.getTransactions({ page: pageNum, per_page: 15 });
    setTransactions(res.data.data);
    setTotalPages(res.data.total_pages);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTransactions(page);
  }, [page, loadTransactions]);

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Transaction history</h1>
      </div>

      {loading && <p>Loading...</p>}

      {!loading && transactions.length === 0 && (
        <div className="empty-state">
          <p>No transactions yet.</p>
        </div>
      )}

      <div className="transaction-table">
        {transactions.map((t) => (
          <div className="transaction-row" key={t.id}>
            <div>
              <div className="transaction-desc">{t.description}</div>
              <div className="transaction-date">
                {new Date(t.created_at).toLocaleDateString()} ·{" "}
                {t.transaction_type.replace("_", " ")}
              </div>
            </div>
            <div className={`transaction-amount ${t.amount < 0 ? "negative" : "positive"}`}>
              {t.amount < 0 ? "-" : "+"}₦{Math.abs(t.amount).toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </DashboardLayout>
  );
}