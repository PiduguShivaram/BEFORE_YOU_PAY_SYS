"use client";

import React, { useRef, useState, useCallback } from "react";

interface Card3DProps {
  children: React.ReactNode;
  className?: string;
  intensity?: number; // Tilt intensity (default: 15deg)
  glare?: boolean; // Show dynamic specular light reflection
  depth?: number; // Visual elevation depth
  onClick?: () => void;
  style?: React.CSSProperties;
}

export function Card3D({
  children,
  className = "",
  intensity = 12,
  glare = true,
  depth = 30,
  onClick,
  style = {},
}: Card3DProps) {
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [transform, setTransform] = useState<string>(
    "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)"
  );
  const [glarePosition, setGlarePosition] = useState<{ x: number; y: number; opacity: number }>({
    x: 50,
    y: 50,
    opacity: 0,
  });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const card = cardRef.current;
      if (!card) return;

      const rect = card.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;

      // Normalized coordinates from -1 to 1
      const xNorm = (clientX / rect.width) * 2 - 1;
      const yNorm = (clientY / rect.height) * 2 - 1;

      const rotX = -yNorm * intensity;
      const rotY = xNorm * intensity;

      setTransform(
        `perspective(1000px) rotateX(${rotX.toFixed(2)}deg) rotateY(${rotY.toFixed(2)}deg) scale3d(1.015, 1.015, 1.015)`
      );

      if (glare) {
        setGlarePosition({
          x: (clientX / rect.width) * 100,
          y: (clientY / rect.height) * 100,
          opacity: 0.22,
        });
      }
    },
    [intensity, glare]
  );

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setTransform("perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)");
    if (glare) {
      setGlarePosition((prev) => ({ ...prev, opacity: 0 }));
    }
  };

  return (
    <div
      ref={cardRef}
      onClick={onClick}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative transform-gpu transition-transform duration-200 ease-out preserve-3d will-change-transform ${className}`}
      style={{
        transform,
        transformStyle: "preserve-3d",
        ...style,
      }}
    >
      {/* 3D Specular Dynamic Glare Sheen */}
      {glare && (
        <div
          className="absolute inset-0 pointer-events-none rounded-[inherit] overflow-hidden z-20 transition-opacity duration-300"
          style={{
            opacity: glarePosition.opacity,
            background: `radial-gradient(circle 350px at ${glarePosition.x}% ${glarePosition.y}%, rgba(255, 255, 255, 0.25), rgba(6, 182, 212, 0.1) 40%, transparent 80%)`,
          }}
        />
      )}

      {/* 3D Drop Shadow Extrusion */}
      <div
        className="absolute inset-0 rounded-[inherit] pointer-events-none transition-shadow duration-300 -z-10"
        style={{
          boxShadow: isHovered
            ? "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px -5px rgba(6, 182, 212, 0.25)"
            : "0 10px 30px -10px rgba(0, 0, 0, 0.5)",
        }}
      />

      {/* Card Content with 3D Preservation */}
      <div className="relative w-full h-full preserve-3d">{children}</div>
    </div>
  );
}
