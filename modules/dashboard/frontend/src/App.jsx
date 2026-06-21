import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./lib/theme";
import { DataProvider } from "./lib/data";
import AppShell from "./components/layout/AppShell";

import Dashboard from "./pages/Dashboard";
import RiskFindings from "./pages/RiskFindings";
import ResourceExplorer from "./pages/ResourceExplorer";
import Analytics from "./pages/Analytics";
import Chat from "./pages/Chat";
import Reports from "./pages/Reports";
import Notifications from "./pages/Notifications";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <ThemeProvider>
      <DataProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/app" replace />} />
            <Route path="/app" element={<AppShell />}>
              <Route index element={<Dashboard />} />
              <Route path="findings" element={<RiskFindings />} />
              <Route path="resources" element={<ResourceExplorer />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="chat" element={<Chat />} />
              <Route path="reports" element={<Reports />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </BrowserRouter>
      </DataProvider>
    </ThemeProvider>
  );
}
