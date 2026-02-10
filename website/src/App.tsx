import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import MoveToTop from "./components/MoveToTop";
import Navbar from "./components/Navbar";

// ✅ Import AOS library and CSS
import AOS from "aos";
import "aos/dist/aos.css";

const queryClient = new QueryClient();

const App: React.FC = () => {
  // ✅ Initialize AOS once on mount
  useEffect(() => {
    AOS.init({
      duration: 800, // Animation duration (ms)
      easing: "ease-in-out", // Smooth transition
      once: true, // Run animation only once
      mirror: false, // Do not animate when scrolling back up
    });
  }, []);

  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <Navbar />
            <Routes>
              <Route path="/" element={<Index />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
            {/* Move to Top button */}
            <MoveToTop />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export default App;
