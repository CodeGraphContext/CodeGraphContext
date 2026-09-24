import { useEffect, useState } from "react";

export default function ScrollButtons() {
  const [showTop, setShowTop] = useState(false);
  const [showBottom, setShowBottom] = useState(true);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;

      setShowTop(scrollTop > 300);
      setShowBottom(scrollTop + windowHeight < documentHeight - 300);
    };

    window.addEventListener("scroll", handleScroll);
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const scrollToBottom = () => {
    window.scrollTo({
      top: document.documentElement.scrollHeight,
      behavior: "smooth",
    });
  };

  return (
    <div className="fixed bottom-6 right-6 flex flex-col gap-3 z-50">
      {showTop && (
        <button
          onClick={scrollToTop}
          className="h-12 w-12 rounded-full bg-purple-600 text-white shadow-lg hover:scale-110 transition"
          aria-label="Scroll to top"
        >
          ↑
        </button>
      )}

      {showBottom && (
        <button
          onClick={scrollToBottom}
          className="h-12 w-12 rounded-full bg-cyan-500 text-white shadow-lg hover:scale-110 transition"
          aria-label="Scroll to bottom"
        >
          ↓
        </button>
      )}
    </div>
  );
}