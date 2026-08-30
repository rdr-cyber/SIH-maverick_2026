import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import CommandCenter from "@/pages/CommandCenter";
import ActorSearch from "@/pages/ActorSearch";
import ActorProfile from "@/pages/ActorProfile";
import Evidence from "@/pages/Evidence";
import Graph from "@/pages/Graph";
import Timeline from "@/pages/Timeline";
import Infrastructure from "@/pages/Infrastructure";
import Monitoring from "@/pages/Monitoring";
import InvestigationWorkspace from "@/pages/InvestigationWorkspace";
import Reports from "@/pages/Reports";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<CommandCenter />} />
          <Route path="actors" element={<ActorSearch />} />
          <Route path="actors/:ref" element={<ActorProfile />} />
          <Route path="evidence" element={<Evidence />} />
          <Route path="graph" element={<Graph />} />
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
