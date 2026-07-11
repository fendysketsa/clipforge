import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClipForge",
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
        <Toaster
          position="top-center"
          gutter={12}
          toastOptions={{
            duration: 3600,
            style: {
              border: "1px solid var(--border)",
              borderRadius: "12px",
              boxShadow: "var(--shadow-md)",
              color: "var(--text-primary)",
              fontSize: "14px",
              fontWeight: 500,
              padding: "12px 14px",
            },
          }}
        />
      </body>
    </html>
  );
}
