import React, { useEffect, useState, useRef } from 'react';
import { useInView } from 'framer-motion';

interface AnimatedCounterProps {
  target: number;
  duration?: number;
  suffix?: string;
  className?: string;
}

const AnimatedCounter: React.FC<AnimatedCounterProps> = ({ 
  target, 
  duration = 2000, 
  suffix = "",
  className = "" 
}) => {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-20px" });

  useEffect(() => {
    if (!isInView || target === 0) return;

    let startTime: number | null = null;
    let animationFrameId: number;

    const easeOutQuart = (x: number): number => {
      return 1 - Math.pow(1 - x, 4);
    };

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = timestamp - startTime;
      const percentage = Math.min(progress / duration, 1);
      
      const easedProgress = easeOutQuart(percentage);
      const currentCount = Math.floor(easedProgress * target);
      
      setCount(currentCount);

      if (percentage < 1) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        setCount(target);
      }
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [target, duration, isInView]);

  // Format large numbers (e.g. 1500 -> 1.5k) if desired, but for now just comma separate
  const formattedCount = count.toLocaleString();

  return (
    <span ref={ref} className={className}>
      {formattedCount}{suffix}
    </span>
  );
};

export default AnimatedCounter;
