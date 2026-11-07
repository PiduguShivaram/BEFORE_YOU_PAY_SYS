"use client";

import React, { useEffect, useRef, useState } from "react";

export function SpatialCursor3D() {
  const cursorDotRef = useRef<HTMLDivElement | null>(null);
  const cursorRingRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isHoveringClickable, setIsHoveringClickable] = useState(false);
  const [isClicking, setIsClicking] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [isTouchDevice, setIsTouchDevice] = useState(false);

  // Position refs for smooth 60fps lerping without React state lag
  const mousePos = useRef({ x: -100, y: -100 });
  const ringPos = useRef({ x: -100, y: -100 });
  const particles = useRef<Array<{ x: number; y: number; vx: number; vy: number; life: number; maxLife: number; color: string }>>([]);

  useEffect(() => {
    // Detect touch-only devices
    if (window.matchMedia("(pointer: coarse)").matches) {
      setIsTouchDevice(true);
      return;
    }

    const handleMouseMove = (e: MouseEvent) => {
      mousePos.current.x = e.clientX;
      mousePos.current.y = e.clientY;
      if (!isVisible) setIsVisible(true);

      // Check if hovering over clickable elements
      const target = e.target as HTMLElement | null;
      if (target) {
        const isClickable = Boolean(
          target.closest("button") ||
          target.closest("a") ||
          target.closest("input") ||
          target.closest("textarea") ||
          target.closest("[role='button']") ||
          target.closest("[role='tab']") ||
          target.closest(".clickable") ||
          target.classList.contains("cursor-pointer")
        );
        setIsHoveringClickable(isClickable);
      }

      // Add a trailing 3D particle
      if (Math.random() > 0.4) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 1.5;
        particles.current.push({
          x: e.clientX,
          y: e.clientY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          life: 1,
          maxLife: 24,
          color: Math.random() > 0.6 ? "#06b6d4" : Math.random() > 0.3 ? "#818cf8" : "#38bdf8",
        });
      }
    };

    const handleMouseDown = () => setIsClicking(true);
    const handleMouseUp = () => setIsClicking(false);
    const handleMouseLeave = () => setIsVisible(false);
    const handleMouseEnter = () => setIsVisible(true);

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);
    document.addEventListener("mouseleave", handleMouseLeave);
    document.addEventListener("mouseenter", handleMouseEnter);

    // Canvas size for particle trail
    const canvas = canvasRef.current;
    let ctx: CanvasRenderingContext2D | null = null;
    if (canvas) {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      ctx = canvas.getContext("2d");
    }

    const handleResize = () => {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    let animationFrameId: number;

    const animate = () => {
      // 1. Smooth interpolation for outer reticle ring
      ringPos.current.x += (mousePos.current.x - ringPos.current.x) * 0.22;
      ringPos.current.y += (mousePos.current.y - ringPos.current.y) * 0.22;

      // Update inner core position directly
      if (cursorDotRef.current) {
        cursorDotRef.current.style.transform = `translate3d(${mousePos.current.x}px, ${mousePos.current.y}px, 0) translate(-50%, -50%)`;
      }

      // Update outer ring with spring damping
      if (cursorRingRef.current) {
        cursorRingRef.current.style.transform = `translate3d(${ringPos.current.x}px, ${ringPos.current.y}px, 0) translate(-50%, -50%)`;
      }

      // 2. Render particle trail on canvas
      if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = particles.current.length - 1; i >= 0; i--) {
          const p = particles.current[i];
          p.x += p.vx;
          p.y += p.vy;
          p.life += 1;

          const progress = p.life / p.maxLife;
          if (progress >= 1) {
            particles.current.splice(i, 1);
            continue;
          }

          const alpha = 1 - progress;
          const radius = Math.max(0.5, (1 - progress) * 2.5);

          ctx.beginPath();
          ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.globalAlpha = alpha * 0.7;
          ctx.shadowBlur = 8;
          ctx.shadowColor = p.color;
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("mouseleave", handleMouseLeave);
      document.removeEventListener("mouseenter", handleMouseEnter);
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isVisible]);

  if (isTouchDevice || !isVisible) {
    return null;
  }

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden">
      {/* 1. Trailing Particle Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full block" />

      {/* 2. Outer 3D Reticle Ring */}
      <div
        ref={cursorRingRef}
        className={`absolute top-0 left-0 transition-[width,height,border-color,background-color] duration-200 ease-out will-change-transform flex items-center justify-center rounded-full pointer-events-none ${
          isHoveringClickable
            ? "w-11 h-11 border-2 border-cyan-400 bg-cyan-400/10 shadow-[0_0_20px_rgba(6,182,212,0.6)]"
            : isClicking
            ? "w-6 h-6 border-2 border-purple-400 bg-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.8)]"
            : "w-8 h-8 border border-cyan-500/50 bg-cyan-500/5 shadow-[0_0_12px_rgba(6,182,212,0.3)]"
        }`}
      >
        {/* Holographic Target Brackets when hovering over interactive elements */}
        {isHoveringClickable && (
          <div className="absolute inset-0 rounded-full animate-spin-slow">
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-1.5 h-0.5 bg-cyan-300" />
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-0.5 bg-cyan-300" />
            <div className="absolute -left-1 top-1/2 -translate-y-1/2 w-0.5 h-1.5 bg-cyan-300" />
            <div className="absolute -right-1 top-1/2 -translate-y-1/2 w-0.5 h-1.5 bg-cyan-300" />
          </div>
        )}
      </div>

      {/* 3. Core Glowing Dot */}
      <div
        ref={cursorDotRef}
        className={`absolute top-0 left-0 rounded-full will-change-transform pointer-events-none transition-[width,height,background-color] duration-150 ${
          isClicking
            ? "w-3 h-3 bg-purple-300 shadow-[0_0_15px_#c084fc]"
            : isHoveringClickable
            ? "w-2 h-2 bg-white shadow-[0_0_12px_#ffffff]"
            : "w-1.5 h-1.5 bg-cyan-400 shadow-[0_0_10px_#06b6d4]"
        }`}
      />
    </div>
  );
}
