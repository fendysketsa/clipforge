import type { Metadata } from "next";
import { AudioNoticeToaster } from "./_components/AudioNoticeToaster";
import "./globals.css";
import { THEME_BOOTSTRAP } from "../lib/studioTheme";

export const metadata: Metadata = {
  title: "ClipForge Studio",
  description: "Ruang produksi video, review hasil, dan otomasi channel.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id" data-theme="dark" suppressHydrationWarning>
      <head><script id="studio-theme-init" dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} /></head>
      <body className="studioApp">
        {children}
        <AudioNoticeToaster />
      </body>
    </html>
  );
}
