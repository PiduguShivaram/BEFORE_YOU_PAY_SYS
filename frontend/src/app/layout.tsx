import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Before You Pay | AI Financial Decision Support",
  description: "Phone-first decision-support platform auditing financial documents, quotations, and bills before payment commitment.",
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
    apple: "/icon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#070b14",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark overflow-x-hidden ${plusJakarta.variable} ${jetbrainsMono.variable}`}>
      <body className="antialiased selection:bg-brand-500/30 selection:text-brand-100 font-sans overflow-x-hidden w-full max-w-full">
        {/* Ambient Top Glow */}
        <div className="fixed top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[750px] max-w-[100vw] h-[450px] bg-gradient-to-b from-brand-500/15 via-sky-500/5 to-transparent rounded-full blur-3xl pointer-events-none z-0" />
        <div className="relative z-10 w-full overflow-x-hidden">{children}</div>
      </body>
    </html>
  );
}
