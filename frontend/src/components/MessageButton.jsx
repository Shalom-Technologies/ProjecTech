import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { messagesApi } from "../services/messages";

export default function MessageButton({ receiverId, projectId, receiverName }) {
  const navigate = useNavigate();
  const [existingConversationId, setExistingConversationId] = useState(null);
  const [checking, setChecking] = useState(true);
  const [showCompose, setShowCompose] = useState(false);
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const checkExisting = useCallback(async () => {
    setChecking(true);
    try {
      const res = await messagesApi.listConversations();
      const match = res.data.data.find(
        (c) => c.project_id === projectId && c.other_participant_id === receiverId
      );
      if (match) {
        setExistingConversationId(match.id);
      }
    } catch {
      // Silently fail — worst case, user sees the compose box instead of a direct link
    } finally {
      setChecking(false);
    }
  }, [projectId, receiverId]);

  useEffect(() => {
    checkExisting();
  }, [checkExisting]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;

    setSending(true);
    setError("");
    try {
      const res = await messagesApi.send({
        receiver_id: receiverId,
        project_id: projectId,
        content: content.trim(),
      });
      navigate(`/dashboard/messages/${res.data.conversation_id}`);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not send message."
      );
      setSending(false);
    }
  };

  if (checking) {
    return (
      <button className="btn-secondary" disabled>
        Loading...
      </button>
    );
  }

  if (existingConversationId) {
    return (
      <button
        className="btn-secondary"
        onClick={() => navigate(`/dashboard/messages/${existingConversationId}`)}
      >
        Message {receiverName}
      </button>
    );
  }

  if (!showCompose) {
    return (
      <button className="btn-secondary" onClick={() => setShowCompose(true)}>
        Message {receiverName}
      </button>
    );
  }

  return (
    <form className="compose-inline" onSubmit={handleSend}>
      {error && <div className="form-error-banner">{error}</div>}
      <textarea
        rows={3}
        placeholder={`Write a message to ${receiverName}...`}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        autoFocus
      />
      <div className="compose-inline-actions">
        <button type="submit" disabled={sending || !content.trim()}>
          {sending ? "Sending..." : "Send"}
        </button>
        <button
          type="button"
          className="btn-text"
          onClick={() => setShowCompose(false)}
          disabled={sending}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}