import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { SocketProvider, useSocket } from "./context/SocketContext";
import ProtectedRoute from "./components/ProtectedRoute";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import DashboardRedirect from "./pages/DashboardRedirect";
import DashboardHome from "./pages/DashboardHome";
import PostProject from "./pages/PostProject";
import MyProjects from "./pages/MyProjects";
import EditProject from "./pages/EditProject";
import ProjectApplications from "./pages/ProjectApplications";
import BrowseProjects from "./pages/BrowseProjects";
import ProjectDetail from "./pages/ProjectDetail";
import MyDevProjects from "./pages/MyDevProjects";
import Conversations from "./pages/Conversations";
import ChatWindow from "./pages/ChatWindow";
import PaymentCallback from "./pages/PaymentCallback";
import Wallet from "./pages/Wallet";
import TransactionHistory from "./pages/TransactionHistory";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings"

function MessageToast() {
  const { toast, dismissToast } = useSocket();
  const navigate = useNavigate();

  if (!toast) return null;

  return (
    <div className="message-toast" onClick={() => {
      navigate(`/dashboard/messages/${toast.conversation_id}`);
      dismissToast();
    }}>
      <strong>{toast.sender_name}</strong>
      <p>{toast.content}</p>
      <button
        className="toast-close"
        onClick={(e) => {
          e.stopPropagation();
          dismissToast();
        }}
      >
        ×
      </button>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <SocketProvider>
        <BrowserRouter>
          <MessageToast />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardRedirect />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard/overview"
              element={
                <ProtectedRoute allowedRoles={["salesperson"]}>
                  <DashboardHome />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/projects"
              element={
                <ProtectedRoute allowedRoles={["salesperson"]}>
                  <MyProjects />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/projects/new"
              element={
                <ProtectedRoute allowedRoles={["salesperson"]}>
                  <PostProject />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/projects/:id/edit"
              element={
                <ProtectedRoute allowedRoles={["salesperson"]}>
                  <EditProject />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/projects/:id/applications"
              element={
                <ProtectedRoute allowedRoles={["salesperson"]}>
                  <ProjectApplications />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard/browse"
              element={
                <ProtectedRoute allowedRoles={["developer"]}>
                  <BrowseProjects />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/browse/:id"
              element={
                <ProtectedRoute allowedRoles={["developer"]}>
                  <ProjectDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/my-projects"
              element={
                <ProtectedRoute allowedRoles={["developer"]}>
                  <MyDevProjects />
                </ProtectedRoute>
              }
            />

            {/* Messaging — shared by both roles */}
            <Route
              path="/dashboard/messages"
              element={
                <ProtectedRoute>
                  <Conversations />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/messages/:conversationId"
              element={
                <ProtectedRoute>
                  <ChatWindow />
                </ProtectedRoute>
              }
            />

            {/* Wallet routes */}
            <Route
              path="/payment/callback"
              element={
                <ProtectedRoute>
                  <PaymentCallback />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/wallet"
              element={
                <ProtectedRoute>
                  <Wallet />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/transactions"
              element={
                <ProtectedRoute>
                  <TransactionHistory />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard/profile"
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/settings"
              element={
                <ProtectedRoute>
                  <Settings />
                </ProtectedRoute>
              }
            />

            <Route path="/" element={<Login />} />
          </Routes>
        </BrowserRouter>
      </SocketProvider>
    </AuthProvider>
  );
}

export default App;