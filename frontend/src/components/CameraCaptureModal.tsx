"use client";

import React, { useRef, useState, useEffect } from "react";
import { Camera, RotateCcw, Check, X, AlertTriangle, RefreshCw } from "lucide-react";

interface CameraCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
  onFallbackToFileInput: () => void;
}

export const CameraCaptureModal: React.FC<CameraCaptureModalProps> = ({
  isOpen,
  onClose,
  onCapture,
  onFallbackToFileInput,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [capturedUrl, setCapturedUrl] = useState<string | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isStartingStream, setIsStartingStream] = useState<boolean>(false);

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const startCamera = async () => {
    setCameraError(null);
    setCapturedBlob(null);
    if (capturedUrl) {
      URL.revokeObjectURL(capturedUrl);
      setCapturedUrl(null);
    }
    setIsStartingStream(true);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError("Live camera streaming is not supported by your browser environment. You can use your device's native camera input instead.");
      setIsStartingStream(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      console.warn("Camera stream request failed:", err);
      let msg = "Could not access camera. Please verify camera permissions in your browser.";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        msg = "Camera permission was denied. You can enable camera permission in your browser or select an existing photo.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        msg = "No camera found on this device. You can upload an image or scan from files.";
      }
      setCameraError(msg);
    } finally {
      setIsStartingStream(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      startCamera();
    } else {
      stopStream();
      if (capturedUrl) {
        URL.revokeObjectURL(capturedUrl);
        setCapturedUrl(null);
      }
      setCapturedBlob(null);
      setCameraError(null);
    }
    return () => {
      stopStream();
    };
  }, [isOpen]);

  const handleCaptureFrame = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (blob) {
          stopStream();
          setCapturedBlob(blob);
          const url = URL.createObjectURL(blob);
          setCapturedUrl(url);
        }
      },
      "image/jpeg",
      0.92
    );
  };

  const handleRetake = () => {
    if (capturedUrl) {
      URL.revokeObjectURL(capturedUrl);
      setCapturedUrl(null);
    }
    setCapturedBlob(null);
    startCamera();
  };

  const handleConfirm = () => {
    if (!capturedBlob) return;
    const filename = `camera_scan_${Date.now()}.jpg`;
    const file = new File([capturedBlob], filename, { type: "image/jpeg" });
    stopStream();
    onCapture(file);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="camera-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div className="w-full max-w-lg surface-card rounded-2xl border border-white/15 bg-slate-950 p-4 sm:p-5 shadow-2xl flex flex-col space-y-3.5">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-brand-400" />
            <h2 id="camera-modal-title" className="font-bold text-sm sm:text-base text-white">
              {capturedBlob ? "Review Captured Document" : "Live Camera Capture"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            aria-label="Close camera modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Viewport or Review Image */}
        <div className="relative w-full aspect-[4/3] sm:aspect-[16/10] bg-black rounded-xl overflow-hidden border border-white/10 flex items-center justify-center">
          {capturedUrl ? (
            <img
              src={capturedUrl}
              alt="Captured document scan"
              className="w-full h-full object-contain"
            />
          ) : cameraError ? (
            <div className="p-4 text-center space-y-3 max-w-sm">
              <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
              <p className="text-xs text-slate-300 leading-relaxed">{cameraError}</p>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onFallbackToFileInput();
                }}
                className="min-h-[48px] px-4 py-2.5 rounded-xl font-bold text-xs bg-brand-500 hover:bg-brand-400 text-white shadow transition active:scale-95 flex items-center justify-center gap-2 mx-auto"
              >
                <Camera className="w-4 h-4" />
                <span>Use Device Native Camera</span>
              </button>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
              {/* Document Alignment Frame */}
              <div className="absolute inset-4 sm:inset-6 border-2 border-dashed border-white/40 rounded-lg pointer-events-none flex flex-col justify-between p-2">
                <span className="text-[10px] text-white/70 font-mono bg-black/60 px-2 py-0.5 rounded self-start">
                  Align document within frame
                </span>
                <span className="text-[10px] text-white/70 font-mono bg-black/60 px-2 py-0.5 rounded self-end">
                  Hold steady
                </span>
              </div>
            </>
          )}

          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* Actions Bar */}
        <div className="flex items-center justify-between gap-2 pt-2">
          {capturedBlob ? (
            <>
              <button
                type="button"
                onClick={handleRetake}
                className="min-h-[48px] flex-1 px-4 py-2.5 rounded-xl font-semibold text-xs sm:text-sm bg-white/10 hover:bg-white/15 text-slate-200 border border-white/10 transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <RotateCcw className="w-4 h-4 text-slate-400" />
                <span>Retake</span>
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="min-h-[48px] flex-1 px-4 py-2.5 rounded-xl font-bold text-xs sm:text-sm bg-brand-500 hover:bg-brand-400 text-white shadow-card transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <Check className="w-4 h-4 text-white" />
                <span>Use Photo & Analyze</span>
              </button>
            </>
          ) : !cameraError ? (
            <>
              <button
                type="button"
                onClick={startCamera}
                disabled={isStartingStream}
                className="min-h-[48px] px-3 py-2 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-white/5 transition flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                title="Restart camera stream"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isStartingStream ? "animate-spin" : ""}`} />
                <span>Reload</span>
              </button>

              <button
                type="button"
                onClick={handleCaptureFrame}
                className="min-h-[52px] flex-1 px-5 py-3 rounded-xl font-bold text-sm sm:text-base bg-emerald-600 hover:bg-emerald-500 text-white shadow-card transition flex items-center justify-center gap-2 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                <Camera className="w-5 h-5 text-white" />
                <span>Capture Document</span>
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};
