import type { Metadata } from "next";
import { AudioNoticeToaster } from "./_components/AudioNoticeToaster";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fendy Clipper",
  description: "Turn long videos into ready-to-post clips",
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
    <html lang="en">
      <body>
        {children}
        <AudioNoticeToaster />
      </body>
    </html>
  );
}
