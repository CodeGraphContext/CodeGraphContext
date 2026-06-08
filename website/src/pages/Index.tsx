import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import HeroSection from "../components/HeroSection";
import FeaturesSection from "../components/FeaturesSection";
import InstallationSection from "../components/InstallationSection";
import DemoSection from "../components/DemoSection";
import ExamplesSection from "../components/ExamplesSection";
import CookbookSection from "../components/CookbookSection";
import Footer from "../components/Footer";
import TestimonialSection from "../components/TestimonialSection";
import SocialMentionsTimeline from "../components/SocialMentionsTimeline";
import ComparisonTable from "../components/ComparisonTable";
import BundleRegistrySection from "../components/BundleRegistrySection";

const Index = () => {
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/pre-indexed" || location.hash === "#bundle-registry") {
      const timer = setTimeout(() => {
        const el = document.getElementById("bundle-registry");
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [location.pathname, location.hash]);

  return (
    <main className="pt-16">
      <div>
        <HeroSection />
      </div>
      <div id="demo">
        <DemoSection />
      </div>
      <div>
        <ComparisonTable />
      </div>
      <div id="features">
        <FeaturesSection />
      </div>
      <div id="installation">
        <InstallationSection />
      </div>
      <div id="bundle-registry">
        <BundleRegistrySection />
      </div>

      <div id="examples">
        <ExamplesSection />
      </div>
      <div id="testimonials">
        <TestimonialSection />
      </div>
      <div id="cookbook">
        <CookbookSection />
      </div>
      <div id="socialmentions">
        <SocialMentionsTimeline />
      </div>
      <div>
        <Footer />
      </div>
    </main>
  );
};

export default Index;

