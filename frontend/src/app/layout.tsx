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
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark overflow-x-hidden ${plusJakarta.variable} ${jetbrainsMono.variable}`}>
      <body className="antialiased selection:bg-brand-500/30 selection:text-brand-100 font-sans overflow-x-hidden w-full max-w-full bg-[#070b14] text-slate-100">
        <div className="relative w-full overflow-x-hidden">{children}</div>
      </body>
    </html>
  );
}
