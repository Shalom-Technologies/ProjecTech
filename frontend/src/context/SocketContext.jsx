import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "./AuthContext";

const SocketContext = createContext(null);

export function SocketProvider({ children }) {
  const { user } = useAuth();
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);
  const activeConversationRef = useRef(null);

  const [onlineUserIds, setOnlineUserIds] = useState(new Set());
  const [lastMessage, setLastMessage] = useState(null);
  const [toast, setToast] = useState(null);

  const setActiveConversation = useCallback((conversationId) => {
    activeConversationRef.current = conversationId;
  }, []);

  useEffect(() => {
  if (!user) return;

  const token = localStorage.getItem("access_token");
  if (!token) return;

  let isActive = true;
  let ws = null;

  function connect() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const rawBase = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, "");
    const base = rawBase.replace(/^https?/, protocol);
    const wsUrl = `${base}/ws/messages?token=${token}`;

    console.log("Connecting to WebSocket:", wsUrl);

    ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.event === "presence_snapshot") {
        setOnlineUserIds(new Set(data.online_user_ids));
      } else if (data.event === "presence_online") {
        setOnlineUserIds((prev) => new Set(prev).add(data.user_id));
      } else if (data.event === "presence_offline") {
        setOnlineUserIds((prev) => {
          const next = new Set(prev);
          next.delete(data.user_id);
          return next;
        });
      } else if (data.event === "new_message") {
        setLastMessage(data);

        if (activeConversationRef.current !== data.conversation_id) {
          setToast({
            id: data.message_id,
            sender_name: data.sender_name,
            content: data.content,
            conversation_id: data.conversation_id,
          });
        }
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    ws.onclose = () => {
      if (isActive) {
        reconnectTimeout.current = setTimeout(connect, 2000);
      }
    };
  }

  connect();

  return () => {
    isActive = false;
    clearTimeout(reconnectTimeout.current);
    ws?.close();
  };
}, [user]);

  const dismissToast = useCallback(() => setToast(null), []);

  return (
    <SocketContext.Provider
      value={{ onlineUserIds, lastMessage, setActiveConversation, toast, dismissToast }}
    >
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error("useSocket must be used within a SocketProvider");
  }
  return context;
}