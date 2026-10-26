import { Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import ChatPage from "@/pages/ChatPage";
import DashboardPage from "@/pages/DashboardPage";
import DocumentDetailPage from "@/pages/DocumentDetailPage";
import DocumentsPage from "@/pages/DocumentsPage";
import NotFoundPage from "@/pages/NotFoundPage";
import SummariesPage from "@/pages/SummariesPage";

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route
          path="documents/:documentId"
          element={<DocumentDetailPage />}
        />
        <Route path="chat" element={<ChatPage />} />
        <Route path="summaries" element={<SummariesPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
