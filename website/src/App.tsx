import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Explore from "./pages/Explore";
import Privacy from "./pages/Privacy";
import PRReviewerPage from "./pages/PRReviewerPage";

import Navbar from "./components/Navbar";

// Removed AOS for instant loading

const queryClient = new QueryClient();

const App: React.FC = () => {

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <Navbar />
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/pre-indexed" element={<Index />} />
              <Route path="/explore" element={<Explore />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/pr-reviewer" element={<PRReviewerPage />} />
              <Route path="/pr-reviewer/:owner/:repo/pull/:prNumber" element={<PRReviewerPage />} />
              <Route path="/github/:owner/:repo" element={<Explore />} />
              <Route path="/gitlab/*" element={<Explore />} />
              <Route path="/:owner/:repo" element={<Explore />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export default App;
