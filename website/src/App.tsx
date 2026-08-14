
import { lazy, Suspense } from "react";
import { Analytics } from "@vercel/analytics/react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Loader2 } from "lucide-react";

const Index = lazy(() => import("./pages/Index"));
const Explore = lazy(() => import("./pages/Explore"));
const Privacy = lazy(() => import("./pages/Privacy"));
const PRReviewerPage = lazy(() => import("./pages/PRReviewerPage"));
const NotFound = lazy(() => import("./pages/NotFound"));

import Navbar from "./components/Navbar";
import MoveToTop from "./components/MoveToTop";

const queryClient = new QueryClient();

const LoadingFallback: React.FC = () => (
  <div className="min-h-screen bg-black flex flex-col items-center justify-center text-white font-mono text-sm gap-3">
    <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
    <span>Loading...</span>
  </div>
);

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
            <Analytics />
            <Toaster />
            <Sonner />
            <Navbar />
            <MoveToTop />
            <Suspense fallback={<LoadingFallback />}>
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
            </Suspense>
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export default App;
