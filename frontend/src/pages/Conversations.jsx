import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { messagesApi } from "../services/messages";
import { useSocket } from "../context/SocketContext";

export default function Conversations() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { onlineUserIds, lastMessage, setActiveConversation } = useSocket();

  const loadConversations = useCallback(async () => {
    try {
      const res = await messagesApi.listConversations();
      setConversations(res.data.data);
    } catch {
      setError("Could not load conversations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setActiveConversation(null); // no chat window open while browsing the list
    loadConversations();
  }, [loadConversations, setActiveConversation]);

  // Refresh the list when any new message arrives, so last-message/unread stay current
  useEffect(() => {
    if (lastMessage) {
      loadConversations();
    }
  }, [lastMessage, loadConversations]);

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Messages</h1>
      </div>

      {loading && <p>Loading conversations...</p>}
      {error && <div className="form-error-banner">{error}</div>}

      {!loading && conversations.length === 0 && (
        <div className="empty-state">
          <p>No conversations yet.</p>
        </div>
      )}

      <div className="conversation-list">
        {conversations.map((conv) => (
          <Link
            to={`/dashboard/messages/${conv.id}`}
            className="conversation-row"
            key={conv.id}
          >
            <div className="conversation-avatar">
              {conv.other_participant_name?.charAt(0) || "?"}
              <span
                className={
                  "presence-dot " +
                  (onlineUserIds.has(conv.other_participant_id) ? "online" : "offline")
                }
              />
            </div>

            <div className="conversation-main">
              <div className="conversation-top">
                <span className="conversation-name">
                  {conv.other_participant_name}
                </span>
                {conv.unread_count > 0 && (
                  <span className="unread-badge">{conv.unread_count}</span>
                )}
              </div>
              <div className="conversation-project">{conv.project_title}</div>
              <div className="conversation-preview">
                {conv.last_message || "No messages yet"}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </DashboardLayout>
  );
}