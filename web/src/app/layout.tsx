import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/public-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Civilian keywords from your service record",
  description:
    "Turn DD-214s, DD-215s and a VMET into civilian job titles, skills and keywords. Runs on this computer.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
