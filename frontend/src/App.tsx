import { Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PersonaProvider } from "@/contexts/PersonaContext";
import { PersistentDiagBot } from "@/components/layout/PersistentDiagBot";
import { HomePage } from "@/pages/HomePage";
import { DiagnoseView } from "@/pages/DiagnoseView";
import { FindMechanicView } from "@/pages/FindMechanicView";
import { PricingPage } from "@/pages/PricingPage";
import { MechanicRegisterPage } from "@/pages/MechanicRegisterPage";
import { MechanicDashboard } from "@/pages/MechanicDashboard";
import { MechanicEditPage } from "@/pages/MechanicEditPage";
import { TrackingView } from "@/pages/TrackingView";
import { MaintenancePage } from "@/pages/MaintenancePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PersonaProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/diagnose" element={<DiagnoseView />} />
          <Route path="/find-mechanic" element={<FindMechanicView />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/mechanic/register" element={<MechanicRegisterPage />} />
          <Route path="/mechanic/dashboard" element={<MechanicDashboard />} />
          <Route path="/mechanic/edit" element={<MechanicEditPage />} />
          <Route path="/tracking/:jobId" element={<TrackingView />} />
          <Route path="/maintenance" element={<MaintenancePage />} />
        </Routes>
        <PersistentDiagBot />
      </PersonaProvider>
    </QueryClientProvider>
  );
}
