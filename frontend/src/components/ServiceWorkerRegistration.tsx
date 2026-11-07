"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker
          .register("/sw.js")
          .then((registration) => {
            console.log("BYP ServiceWorker registered successfully:", registration.scope);
          })
          .catch((error) => {
            console.warn("BYP ServiceWorker registration failed:", error);
          });
      });
    }
  }, []);

  return null;
}
