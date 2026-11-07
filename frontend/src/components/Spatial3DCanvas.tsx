"use client";

import React, { useEffect, useRef, useState } from "react";

interface Spatial3DCanvasProps {
  mode?: "antigravity" | "cyber" | "minimal";
  className?: string;
}

export function Spatial3DCanvas({ mode = "antigravity", className = "" }: Spatial3DCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mouseRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    const handleMouseMove = (e: MouseEvent) => {
      // Normalized between -1 and 1
      mouseRef.current.targetX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.targetY = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("mousemove", handleMouseMove);

    // 1. Initialize 3D Stars & Floating Financial Nodes
    const particleCount = mode === "cyber" ? 140 : 90;
    const particles = Array.from({ length: particleCount }, () => ({
      x: (Math.random() - 0.5) * 2200,
      y: (Math.random() - 0.5) * 1600,
      z: Math.random() * 1200 + 100, // Depth from 100 to 1300
      size: Math.random() * 2 + 1,
      speedZ: Math.random() * 0.8 + 0.3,
      colorType: Math.random() > 0.75 ? "cyan" : Math.random() > 0.5 ? "gold" : "indigo",
    }));

    // 2. 3D Floating Geometric Polyhedra (Shield & Diamond wireframes)
    const shapes = [
      {
        type: "diamond",
        baseX: -450,
        baseY: -120,
        baseZ: 600,
        rotX: 0.2,
        rotY: 0.3,
        rotZ: 0.1,
        rotSpeedX: 0.008,
        rotSpeedY: 0.012,
        scale: 65,
        color: "#06b6d4",
      },
      {
        type: "cube",
        baseX: 480,
        baseY: 140,
        baseZ: 550,
        rotX: 0.4,
        rotY: 0.1,
        rotZ: 0.3,
        rotSpeedX: 0.006,
        rotSpeedY: 0.01,
        scale: 55,
        color: "#818cf8",
      },
      {
        type: "octahedron",
        baseX: 350,
        baseY: -220,
        baseZ: 750,
        rotX: 0.1,
        rotY: 0.5,
        rotZ: 0.2,
        rotSpeedX: 0.009,
        rotSpeedY: 0.007,
        scale: 45,
        color: "#38bdf8",
      },
      {
        type: "shield",
        baseX: -380,
        baseY: 260,
        baseZ: 700,
        rotX: 0.3,
        rotY: 0.2,
        rotZ: 0.4,
        rotSpeedX: 0.007,
        rotSpeedY: 0.011,
        scale: 50,
        color: "#10b981",
      },
    ];

    // 3D Projection Helper
    const focalLength = 450;
    const project = (x: number, y: number, z: number, cameraX: number, cameraY: number) => {
      const adjustedX = x - cameraX;
      const adjustedY = y - cameraY;
      const adjustedZ = Math.max(z, 20);
      const scale = focalLength / adjustedZ;
      return {
        x: width / 2 + adjustedX * scale,
        y: height / 2 + adjustedY * scale,
        scale,
        visible: adjustedZ > 10,
      };
    };

    // 3D Vector Math Helpers for Wireframes
    const rotate3D = (
      p: [number, number, number],
      rx: number,
      ry: number,
      rz: number
    ): [number, number, number] => {
      let [x, y, z] = p;
      // Rotate X
      const cosX = Math.cos(rx);
      const sinX = Math.sin(rx);
      let y1 = y * cosX - z * sinX;
      let z1 = y * sinX + z * cosX;

      // Rotate Y
      const cosY = Math.cos(ry);
      const sinY = Math.sin(ry);
      let x2 = x * cosY + z1 * sinY;
      let z2 = -x * sinY + z1 * cosY;

      // Rotate Z
      const cosZ = Math.cos(rz);
      const sinZ = Math.sin(rz);
      let x3 = x2 * cosZ - y1 * sinZ;
      let y3 = x2 * sinZ + y1 * cosZ;

      return [x3, y3, z2];
    };

    // Shape Geometry Vertices & Edges
    const octahedronVertices: [number, number, number][] = [
      [0, -1, 0],
      [1, 0, 0],
      [0, 0, 1],
      [-1, 0, 0],
      [0, 0, -1],
      [0, 1, 0],
    ];
    const octahedronEdges = [
      [0, 1], [0, 2], [0, 3], [0, 4],
      [5, 1], [5, 2], [5, 3], [5, 4],
      [1, 2], [2, 3], [3, 4], [4, 1],
    ];

    const cubeVertices: [number, number, number][] = [
      [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
      [-1, -1, 1],  [1, -1, 1],  [1, 1, 1],  [-1, 1, 1],
    ];
    const cubeEdges = [
      [0, 1], [1, 2], [2, 3], [3, 0],
      [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
    ];

    let time = 0;

    const render = () => {
      time += 0.015;

      // Smooth camera interpolation following mouse
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;

      const camX = mouseRef.current.x * 120;
      const camY = mouseRef.current.y * 90;

      ctx.clearRect(0, 0, width, height);

      // ─── A. 3D PERSPECTIVE HORIZON GRID (Cyber Synthwave Floor) ───
      const gridZMin = 150;
      const gridZMax = 1200;
      const gridY = 320; // Horizon floor offset
      const gridStep = 45;

      ctx.save();
      ctx.lineWidth = 1;

      // Draw longitudinal depth lines converging to vanishing horizon
      for (let x = -800; x <= 800; x += gridStep * 2) {
        const pNear = project(x, gridY, gridZMin, camX, camY);
        const pFar = project(x, gridY, gridZMax, camX, camY);
        if (pNear.visible && pFar.visible) {
          const grad = ctx.createLinearGradient(pNear.x, pNear.y, pFar.x, pFar.y);
          grad.addColorStop(0, "rgba(99, 102, 241, 0.2)");
          grad.addColorStop(0.6, "rgba(6, 182, 212, 0.12)");
          grad.addColorStop(1, "rgba(6, 182, 212, 0)");
          ctx.strokeStyle = grad;
          ctx.beginPath();
          ctx.moveTo(pNear.x, pNear.y);
          ctx.lineTo(pFar.x, pFar.y);
          ctx.stroke();
        }
      }

      // Draw horizontal crosslines moving forward towards camera
      const speedOffset = (time * 60) % 60;
      for (let z = gridZMin + speedOffset; z < gridZMax; z += 60) {
        const pLeft = project(-800, gridY, z, camX, camY);
        const pRight = project(800, gridY, z, camX, camY);
        if (pLeft.visible && pRight.visible) {
          const alpha = Math.max(0, (1 - (z - gridZMin) / (gridZMax - gridZMin)) * 0.22);
          ctx.strokeStyle = `rgba(6, 182, 212, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(pLeft.x, pLeft.y);
          ctx.lineTo(pRight.x, pRight.y);
          ctx.stroke();
        }
      }
      ctx.restore();

      // ─── B. 3D FLOATING PARTICLES & STARS ───
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.z -= p.speedZ;
        if (p.z < 80) {
          p.z = 1200;
          p.x = (Math.random() - 0.5) * 2000;
          p.y = (Math.random() - 0.5) * 1400;
        }

        const proj = project(p.x, p.y, p.z, camX, camY);
        if (proj.visible) {
          const alpha = Math.min(1, Math.max(0.1, (1200 - p.z) / 1000));
          const radius = Math.max(0.8, p.size * proj.scale);

          ctx.beginPath();
          ctx.arc(proj.x, proj.y, radius, 0, Math.PI * 2);

          if (p.colorType === "cyan") {
            ctx.fillStyle = `rgba(6, 182, 212, ${alpha * 0.8})`;
          } else if (p.colorType === "gold") {
            ctx.fillStyle = `rgba(245, 158, 11, ${alpha * 0.8})`;
          } else {
            ctx.fillStyle = `rgba(129, 140, 248, ${alpha * 0.7})`;
          }
          ctx.fill();

          // Connect nearby particles for 3D constellation effect
          if (i % 3 === 0 && i + 1 < particles.length) {
            const nextP = particles[i + 1];
            const dist = Math.hypot(p.x - nextP.x, p.y - nextP.y, p.z - nextP.z);
            if (dist < 220) {
              const projNext = project(nextP.x, nextP.y, nextP.z, camX, camY);
              ctx.strokeStyle = `rgba(99, 102, 241, ${alpha * 0.15})`;
              ctx.lineWidth = 0.6;
              ctx.beginPath();
              ctx.moveTo(proj.x, proj.y);
              ctx.lineTo(projNext.x, projNext.y);
              ctx.stroke();
            }
          }
        }
      }

      // ─── C. 3D ROTATING POLYHEDRAL WIREFRAMES ───
      shapes.forEach((shape, idx) => {
        shape.rotX += shape.rotSpeedX;
        shape.rotY += shape.rotSpeedY;

        // Floating hover motion
        const floatY = Math.sin(time * 1.5 + idx) * 25;
        const currentY = shape.baseY + floatY;

        const verts = shape.type === "cube" ? cubeVertices : octahedronVertices;
        const edges = shape.type === "cube" ? cubeEdges : octahedronEdges;

        const projectedVerts = verts.map((v) => {
          const rotated = rotate3D(v, shape.rotX, shape.rotY, shape.rotZ);
          const worldX = shape.baseX + rotated[0] * shape.scale;
          const worldY = currentY + rotated[1] * shape.scale;
          const worldZ = shape.baseZ + rotated[2] * shape.scale;
          return project(worldX, worldY, worldZ, camX, camY);
        });

        // Draw wireframe edges
        ctx.save();
        ctx.strokeStyle = shape.color;
        ctx.lineWidth = 1.2;
        ctx.shadowColor = shape.color;
        ctx.shadowBlur = 12;

        edges.forEach(([i1, i2]) => {
          const p1 = projectedVerts[i1];
          const p2 = projectedVerts[i2];
          if (p1?.visible && p2?.visible) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        });

        // Draw vertex nodes
        projectedVerts.forEach((pv) => {
          if (pv?.visible) {
            ctx.beginPath();
            ctx.arc(pv.x, pv.y, 2 * pv.scale, 0, Math.PI * 2);
            ctx.fillStyle = "#ffffff";
            ctx.fill();
          }
        });

        ctx.restore();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, [mode]);

  return (
    <div className={`fixed inset-0 pointer-events-none z-0 overflow-hidden bg-[#070b14] ${className}`}>
      {/* Dynamic 3D ambient radial spotlights */}
      <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full bg-cyan-600/10 blur-[140px] -translate-x-1/2 -translate-y-1/2" />
      <div className="absolute top-2/3 right-1/4 w-[700px] h-[700px] rounded-full bg-indigo-600/10 blur-[160px] translate-x-1/3 -translate-y-1/3" />
      <div className="absolute bottom-10 left-1/2 w-[500px] h-[350px] rounded-full bg-emerald-600/10 blur-[130px] -translate-x-1/2" />
      
      {/* 3D WebGL Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full block" />
    </div>
  );
}
