import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { messagesApi } from "../services/messages";
import { useSocket } from "../context/SocketContext";
import { useAuth } from "../context/AuthContext";

export default function ChatWindow() {
  const { conversationId } = useParams();
  const { user } = useAuth();
  const { onlineUserIds, lastMessage, setActiveConversation } = useSocket();

  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  const bottomRef = useRef(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [convRes, msgRes] = await Promise.all([
        messagesApi.getConversation(conversationId),
        messagesApi.getMessages(conversationId, { per_page: 50 }),
      ]);
      setConversation(convRes.data);
      setMessages(msgRes.data.data);
    } catch {
      setError("Could not load this conversation.");
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    setActiveConversation(conversationId);
    loadData();
    return () => setActiveConversation(null);
  }, [conversationId, loadData, setActiveConversation]);

  // Append live messages that belong to this open conversation
  useEffect(() => {
    if (lastMessage && lastMessage.conversation_id === conversationId) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === lastMessage.message_id)) return prev;
        return [
          ...prev,
          {
            id: lastMessage.message_id,
            sender_id: lastMessage.sender_id,
            sender_name: lastMessage.sender_name,
            content: lastMessage.content,
            created_at: lastMessage.created_at,
            is_read: true,
          },
        ];
      });
    }
  }, [lastMessage, conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!draft.trim() || !conversation) return;

    setSending(true);
    const content = draft.trim();
    setDraft("");

    try {
      const res = await messagesApi.send({
        receiver_id: conversation.other_participant_id,
        project_id: conversation.project_id,
        content,
      });

      // Append immediately — don't wait for the socket echo
      setMessages((prev) => [
        ...prev,
        {
          id: res.data.message_id,
          sender_id: user.id,
          sender_name: `${user.first_name} ${user.last_name}`,
          content,
          created_at: new Date().toISOString(),
          is_read: false,
        },
      ]);
    } catch (err) {
      setError(
        err.response?.data?.message ||
          err.response?.data?.detail ||
          "Could not send message."
      );
      setDraft(content);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <p>Loading conversation...</p>
      </DashboardLayout>
    );
  }

  if (error && !conversation) {
    return (
      <DashboardLayout>
        <div className="form-error-banner">{error}</div>
      </DashboardLayout>
    );
  }

  const isOnline = onlineUserIds.has(conversation.other_participant_id);

  return (
    <DashboardLayout>
      <Link to="/dashboard/messages" className="back-link">
        ← Back to messages
      </Link>

      <div className="chat-window">
        <div className="chat-header">
          <div className="conversation-avatar">
            {conversation.other_participant_name?.charAt(0) || "?"}
            <span className={"presence-dot " + (isOnline ? "online" : "offline")} />
          </div>
          <div>
            <div className="chat-header-name">{conversation.other_participant_name}</div>
            <div className="chat-header-status">
              {isOnline ? "Online" : "Offline"} · {conversation.project_title}
            </div>
          </div>
        </div>

        <div className="chat-messages">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={
                "chat-bubble " +
                (msg.sender_id === user.id ? "chat-bubble-mine" : "chat-bubble-theirs")
              }
            >
              <div className="chat-bubble-content">{msg.content}</div>
              <div className="chat-bubble-time">
                {new Date(msg.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form className="chat-input-row" onSubmit={handleSend}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message..."
            disabled={sending}
          />
          <button type="submit" disabled={sending || !draft.trim()}>
            Send
          </button>
        </form>
      </div>
    </DashboardLayout>
  );
}