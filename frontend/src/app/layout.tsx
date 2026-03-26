import type {Metadata} from "next";
import {Inter} from "next/font/google";
import "./globals.css";
import {Toaster} from "react-hot-toast";

const inter = Inter({subsets: ["latin"]});

export const metadata: Metadata = {
  title: "PanelForge — AI Comic Generator",
  description: "Turn any story into manga, manhwa, or comics using AI",
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[#0d0d1a] text-white min-h-screen`}>
        <Toaster position="top-right" toastOptions={{style: {background: "#1a1a2e", color: "#fff", border: "1px solid #7c3aed"}}} />
        {children}
      </body>
    </html>
  );
}
