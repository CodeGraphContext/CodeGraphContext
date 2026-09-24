import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import "./scroll-performance.css";
import { initScrollPerformance } from "./scrollPerformance";

import "aos/dist/aos.css";

// Initialize scroll performance optimizations
initScrollPerformance();

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
