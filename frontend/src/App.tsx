import { Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PersonaProvider } from "@/contexts/PersonaContext";
import { HomePage } from "@/pages/HomePage";
import { DiagnoseView } from "@/pages/DiagnoseView";
import { PricingPage } from "@/pages/PricingPage";

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
        <Route path="/pricing" element={<PricingPage />} />
        </Routes>
      </PersonaProvider>
    </QueryClientProvider>
  );
}
