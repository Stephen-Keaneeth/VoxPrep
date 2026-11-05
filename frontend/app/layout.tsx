import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VOXPREP — AI Interview & Communication Platform",
  description: "Minimal, elegant, voice-first AI platform for mock interviews and communication coaching.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen flex text-slate-100 bg-[#0b1120]`}>
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 bg-[#0c1322]">
          <Header />
          <main className="p-8 max-w-6xl mx-auto w-full">{children}</main>
        </div>
      </body>
    </html>
  );
}

