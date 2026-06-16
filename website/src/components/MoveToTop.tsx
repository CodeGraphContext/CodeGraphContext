import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronUp, ChevronDown } from "lucide-react";

const MoveToTop: React.FC = () => {
    const [showButton, setShowButton] = useState<boolean>(false);

    useEffect(() => {
        const handleScroll = () => {
            if (window.scrollY > window.innerHeight * 0.05) {
                setShowButton(true);
            } else {
                setShowButton(false);
            }
        };

        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

    const scrollToBottom = () => {
        window.scrollTo({
            top: document.documentElement.scrollHeight,
            behavior: "smooth",
        });
    };

    return (
        <AnimatePresence>
            {showButton && (
                <div
                    style={{
                        position: "fixed",
                        bottom: "40px",
                        right: "40px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                        zIndex: 99,
                    }}
                >
                    {/* Scroll To Top Button */}
                    <motion.button
                        initial={{ opacity: 0, scale: 0.5, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.5, y: 20 }}
                        whileHover={{ scale: 1.1, y: -2 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={scrollToTop}
                        className="w-12 h-12 rounded-full bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] flex items-center justify-center border border-black/20"
                        aria-label="Scroll to top"
                    >
                        <ChevronUp className="w-6 h-6 text-white" />
                    </motion.button>

                    {/* Scroll To Bottom Button */}
                    <motion.button
                        initial={{ opacity: 0, scale: 0.5, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.5, y: 20 }}
                        whileHover={{ scale: 1.1, y: 2 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={scrollToBottom}
                        className="w-12 h-12 rounded-full bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] flex items-center justify-center border border-black/20"
                        aria-label="Scroll to bottom"
                    >
                        <ChevronDown className="w-6 h-6 text-white" />
                    </motion.button>
                </div>
            )}
        </AnimatePresence>
    );
};

export default MoveToTop;