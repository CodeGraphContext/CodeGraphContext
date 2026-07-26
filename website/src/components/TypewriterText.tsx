import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface TypewriterTextProps {
  text: string;
  speed?: number; // ms per char
  delay?: number; // initial delay in ms
  className?: string;
  onComplete?: () => void;
}

const TypewriterText: React.FC<TypewriterTextProps> = ({
  text,
  speed = 50,
  delay = 0,
  className = "",
  onComplete
}) => {
  const [displayedText, setDisplayedText] = useState('');
  const [started, setStarted] = useState(false);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    const startTimer = setTimeout(() => {
      setStarted(true);
    }, delay);
    return () => clearTimeout(startTimer);
  }, [delay]);

  useEffect(() => {
    if (!started) return;

    if (displayedText.length < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText(text.slice(0, displayedText.length + 1));
      }, speed);
      return () => clearTimeout(timeout);
    } else if (!completed) {
      setCompleted(true);
      if (onComplete) onComplete();
    }
  }, [displayedText, started, text, speed, completed, onComplete]);

  return (
    <span className={`inline-block ${className}`}>
      {displayedText}
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
        className="inline-block w-1 md:w-2 bg-current ml-1"
        style={{ height: '0.9em', verticalAlign: 'baseline', display: completed ? 'none' : 'inline-block' }}
      />
    </span>
  );
};

export default TypewriterText;
