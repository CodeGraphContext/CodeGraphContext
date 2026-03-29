import { motion } from "framer-motion";
import { useEffect, useState } from "react";

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
  colorClass: string;
  isOrb: boolean;
  driftX: string;
  driftY: string;
}

const ParticlesBackground = () => {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    const newParticles: Particle[] = [];
    
    // 1. Generate small stardust
    for (let i = 0; i < 50; i++) {
      newParticles.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 3 + 1,
        duration: Math.random() * 20 + 20,
        delay: Math.random() * -20, // Negative delay so it starts mid-animation
        colorClass: Math.random() > 0.6 ? "bg-primary" : "bg-accent",
        isOrb: false,
        driftX: `${(Math.random() - 0.5) * 15}vw`,
        driftY: `${(Math.random() - 0.5) * 15}vh`,
      });
    }

    // 2. Generate large blurry orbs
    for (let i = 0; i < 4; i++) {
      newParticles.push({
        id: i + 100,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 250 + 150,
        duration: Math.random() * 30 + 30,
        delay: Math.random() * -30,
        colorClass: i % 2 === 0 ? "bg-primary/20" : "bg-accent/20",
        isOrb: true,
        driftX: `${(Math.random() - 0.5) * 30}vw`,
        driftY: `${(Math.random() - 0.5) * 30}vh`,
      });
    }

    setParticles(newParticles);
  }, []);

  return (
    <div className="fixed inset-0 pointer-events-none z-[-1] overflow-hidden">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className={`absolute rounded-full ${p.colorClass} ${p.isOrb ? 'blur-[80px]' : 'blur-[1px]'} mix-blend-screen opacity-0`}
          style={{
            width: p.size,
            height: p.size,
            left: `${p.x}vw`,
            top: `${p.y}vh`,
          }}
          animate={{
            y: ["0vh", p.driftY, "0vh"],
            x: ["0vw", p.driftX, "0vw"],
            opacity: p.isOrb ? [0.1, 0.4, 0.1] : [0.1, 0.7, 0.1],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            ease: "easeInOut",
            delay: p.delay,
          }}
        />
      ))}
    </div>
  );
};

export default ParticlesBackground;
