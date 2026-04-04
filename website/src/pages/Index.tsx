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
import BundleGeneratorSection from "../components/BundleGeneratorSection";
import BundleRegistrySection from "../components/BundleRegistrySection";

const Index = () => {
  return (
    <main className="min-h-screen overflow-x-hidden pt-16">
      <div data-aos="fade-in">
        <HeroSection />
      </div>
      <div data-aos="fade-up" id="demo">
        <DemoSection />
      </div>
      <div data-aos="fade-up">
        <ComparisonTable />
      </div>
      <div data-aos="fade-up" id="features">
        <FeaturesSection />
      </div>
      <div data-aos="fade-up" id="installation">
        <InstallationSection />
      </div>
      <div data-aos="fade-up" id="bundleregistry">
        <BundleRegistrySection />
      </div>
      <div data-aos="fade-up" id="bundlegenerator">
        <BundleGeneratorSection />
      </div>
      <div data-aos="fade-up" id="examples">
        <ExamplesSection />
      </div>
      <div data-aos="fade-up" id="testimonials">
        <TestimonialSection />
      </div>
      <div data-aos="fade-up" id="cookbook">
        <CookbookSection />
      </div>
      <div data-aos="fade-up" id="socialmentions">
        <SocialMentionsTimeline />
      </div>
      <div data-aos="fade-up" data-aos-anchor-placement="top-bottom">
        <Footer />
      </div>
    </main>
  );
};

export default Index;

