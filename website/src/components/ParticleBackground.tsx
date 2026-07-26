import React, { useEffect, useRef } from 'react';

interface ParticleBackgroundProps {
  className?: string;
  opacity?: number;
}

const ParticleBackground: React.FC<ParticleBackgroundProps> = ({ 
  className = "",
  opacity = 0.4 
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let particles: Particle[] = [];
    
    // Set canvas dimensions
    const resizeCanvas = () => {
      if (canvas.parentElement) {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
      }
    };

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Particle class
    class Particle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      color: string;

      constructor() {
        this.x = Math.random() * canvas!.width;
        this.y = Math.random() * canvas!.height;
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;
        this.radius = Math.random() * 2 + 1;
        
        // Colors corresponding to --graph-node-1, 2, 3
        const colors = [
          'hsla(263, 70%, 65%, 0.8)',
          'hsla(180, 100%, 70%, 0.8)',
          'hsla(142, 76%, 65%, 0.8)'
        ];
        this.color = colors[Math.floor(Math.random() * colors.length)];
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;

        // Bounce off edges
        if (this.x < 0 || this.x > canvas!.width) this.vx *= -1;
        if (this.y < 0 || this.y > canvas!.height) this.vy *= -1;
      }

      draw() {
        if (!ctx) return;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
        
        // Subtle glow
        ctx.shadowBlur = 10;
        ctx.shadowColor = this.color;
      }
    }

    // Initialize particles (fewer for performance)
    const initParticles = () => {
      particles = [];
      const particleCount = Math.min(Math.floor((canvas.width * canvas.height) / 25000), 50);
      for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
      }
    };

    initParticles();

    // Draw lines between nearby particles
    const drawConnections = () => {
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 150) {
            if (!ctx) continue;
            ctx.beginPath();
            // Opacity based on distance
            const lineOpacity = 1 - (distance / 150);
            ctx.strokeStyle = `rgba(148, 163, 184, ${lineOpacity * 0.2})`;
            ctx.lineWidth = 1;
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
    };

    // Animation loop
    const animate = () => {
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.shadowBlur = 0; // Reset shadow for background clear

      // Update and draw
      particles.forEach(p => {
        p.update();
        p.draw();
      });

      // Turn off shadow for connections
      ctx.shadowBlur = 0;
      drawConnections();

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className={`absolute inset-0 pointer-events-none overflow-hidden ${className}`} style={{ opacity }}>
      <canvas ref={canvasRef} className="w-full h-full block" />
    </div>
  );
};

export default ParticleBackground;
