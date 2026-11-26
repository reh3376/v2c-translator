import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/public-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "./theme.css";
import "./globals.css";
import { BOOT_SCRIPT } from "@/theme/choice";

export const metadata: Metadata = {
  title: "Civilian keywords from your service record",
  description:
    "Turn DD-214s, DD-215s and a VMET into civilian job titles, skills and keywords. Runs on this computer.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // `suppressHydrationWarning`, because the boot script below writes `data-theme` on this
    // element before React arrives, which is the whole point of running it here.
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Ahead of the first paint, so a reader who chose dark never sees a white page. */}
        <script dangerouslySetInnerHTML={{ __html: BOOT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
