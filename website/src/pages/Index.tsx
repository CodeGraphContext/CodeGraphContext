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
    <main className="min-h-screen overflow-x-hidden">
      <div data-aos="fade-in">
        <HeroSection />
      </div>
      <div data-aos="fade-up">
        <DemoSection />
      </div>
      <div data-aos="fade-up">
        <ComparisonTable />
      </div>
      <div data-aos="fade-up">
        <FeaturesSection />
      </div>
      <div data-aos="fade-up">
        <InstallationSection />
      </div>
      <div data-aos="fade-up">
        <BundleRegistrySection />
      </div>
      <div data-aos="fade-up">
        <BundleGeneratorSection />
      </div>
      <div data-aos="fade-up">
        <ExamplesSection />
      </div>
      <div data-aos="fade-up">
        <TestimonialSection />
      </div>
      <div data-aos="fade-up">
        <CookbookSection />
      </div>
      <div data-aos="fade-up">
        <SocialMentionsTimeline />
      </div>
      <div data-aos="fade-up" data-aos-anchor-placement="top-bottom">
        <Footer />
      </div>
    </main>
  );
};

export default Index;

