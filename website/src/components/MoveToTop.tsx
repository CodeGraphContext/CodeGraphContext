import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronUp } from "lucide-react";

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
        behavior: "smooth", });
    };

    return (
        <>
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
        {/* Scroll To Top */}
        <button
            onClick={scrollToTop}
            data-aos="fade-in"
            data-aos-duration="300"
            style={{
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                border: "none",
                background:
                    "linear-gradient(135deg, hsl(263 70% 65%), hsl(180 100% 70%))",
                color: "#fff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 0,
            }}
        >
            <div
                style={{
                    width: "14px",
                    height: "14px",
                    borderTop: "1.5px solid black",
                    borderLeft: "1.5px solid black",
                    transform:
                        "rotate(45deg) translateY(3px) translateX(2px)",
                }}
            />
        </button>

        {/* Scroll To Bottom */}
        <button
            onClick={scrollToBottom}
            data-aos="fade-in"
            data-aos-duration="300"
            style={{
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                border: "none",
                background:
                    "linear-gradient(135deg, hsl(263 70% 65%), hsl(180 100% 70%))",
                color: "#fff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 0,
            }}
        >
            <div
                style={{
                    width: "14px",
                    height: "14px",
                    borderBottom: "1.5px solid black",
                    borderRight: "1.5px solid black",
                    transform:
                        "rotate(45deg) translateY(-2px) translateX(-2px)",
                }}
            />
        </button>
    </div>
        )}
        </>
        <AnimatePresence>
            {showButton && (
                <motion.button
                    initial={{ opacity: 0, scale: 0.5, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.5, y: 20 }}
                    whileHover={{ scale: 1.1, y: -2 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={scrollToTop}
                    className="fixed bottom-10 right-10 w-12 h-12 rounded-full bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(168,85,247,0.4)] flex items-center justify-center z-[99] border border-black/20"
                    aria-label="Scroll to top"
                >
                    <ChevronUp className="w-6 h-6 text-white" />
                </motion.button>
            )}
        </AnimatePresence>
    );
};

export default MoveToTop;
