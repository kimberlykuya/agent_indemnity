import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://agent-indemnity.vercel.app"),
  title: {
    default: "Agent Indemnity",
    template: "%s | Agent Indemnity",
  },
  description: "Wallet-bound AI request payments with Arc-backed slashing and beneficiary-visible accountability.",
  applicationName: "Agent Indemnity",
  keywords: [
    "Agent Indemnity",
    "Arc",
    "Circle",
    "Gemini",
    "FastAPI",
    "Next.js",
    "performance bond",
  ],
  openGraph: {
    title: "Agent Indemnity",
    description: "Wallet-bound AI request payments with Arc-backed slashing and beneficiary-visible accountability.",
    url: "/",
    siteName: "Agent Indemnity",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Agent Indemnity",
    description: "Wallet-bound AI request payments with Arc-backed slashing and beneficiary-visible accountability.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
