import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronUp } from "lucide-react";

const MoveToTop: React.FC = () => {
    const [showButton, setShowButton] = useState<boolean>(false);

    useEffect(() => {
        const handleScroll = () => {
            if (window.scrollY > window.innerHeight * 0.5) {
                setShowButton(true);
            }
            else{
                setShowButton(false);
            }
        };

        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    };
  return (
    <AnimatePresence>
      {showButton && (
        <motion.button
          initial={{ opacity: 0, scale: 0.5, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.5, y: 20 }}
          whileHover={{ scale: 1.1, y: -2 }}
          whileTap={{ scale: 0.9 }}
          onClick={scrollToTop}
          className="fixed bottom-6 right-6 sm:bottom-10 sm:right-10 z-[99] w-11 h-11 sm:w-12 sm:h-12 rounded-full bg-gradient-to-r from-purple-600 to-cyan-500 hover:opacity-90 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)] flex items-center justify-center transition-opacity duration-300"
          aria-label="Scroll to top"
        >
          <ChevronUp className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
        </motion.button>
      )}
    </AnimatePresence>
  );
};

export default MoveToTop;
