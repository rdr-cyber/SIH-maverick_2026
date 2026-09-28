import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import Login from "@/pages/Login";
import CommandCenter from "@/pages/CommandCenter";
import ActorSearch from "@/pages/ActorSearch";
import ActorProfile from "@/pages/ActorProfile";
import Evidence from "@/pages/Evidence";
import Graph from "@/pages/Graph";
import Map from "@/pages/Map";
import Timeline from "@/pages/Timeline";
import Infrastructure from "@/pages/Infrastructure";
import Monitoring from "@/pages/Monitoring";
import InvestigationWorkspace from "@/pages/InvestigationWorkspace";
import Reports from "@/pages/Reports";
import {
  getToken,
  getStoredUser,
  logout as apiLogout,
  type LoginResponse,
  type UserInfo,
} from "@/api/auth";

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getToken());

  // Check if token is still valid on mount
  useEffect(() => {
    if (token && !user) {
      // Token exists but no user info — try to fetch
      import("@/api/auth").then(({ fetchMe }) =>
        fetchMe()
          .then((u) => {
            setUser(u);
            setToken(getToken());
          })
          .catch(() => {
            // Token invalid — clear
            setToken(null);
            setUser(null);
          })
      );
    }
  }, [token, user]);

  const handleLogin = (result: LoginResponse) => {
    setToken(result.access_token);
    setUser({
      username: result.username,
      role: result.role,
      full_name: result.full_name,
      email: "",
      is_active: true,
    });
  };

  const handleLogout = async () => {
    await apiLogout();
    setToken(null);
    setUser(null);
  };

  // Update document title
  useEffect(() => {
    document.title = token ? "TRILOK TRACE" : "TRILOK TRACE — Sign In";
  }, [token]);

  // Not authenticated — show login
  if (!token || !user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout user={user} onLogout={handleLogout} />}>
          <Route index element={<CommandCenter />} />
          <Route path="actors" element={<ActorSearch />} />
          <Route path="actors/:ref" element={<ActorProfile />} />
          <Route path="evidence" element={<Evidence />} />
          <Route path="graph" element={<Graph />} />
          <Route path="map" element={<Map />} />
          <Route path="timeline" element={<Timeline />} />
          <Route path="infrastructure" element={<Infrastructure />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="investigations" element={<InvestigationWorkspace />} />
          <Route path="reports" element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
