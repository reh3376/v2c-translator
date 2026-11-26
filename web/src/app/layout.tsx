import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/public-sans";
import "@fontsource/ibm-plex-mono/400.css";
import "./theme.css";
import "./globals.css";
import { COPY } from "@/content/copy";
import { serverConfig } from "@/server/config";
import { BOOT_SCRIPT } from "@/theme/choice";

/** Read per request, like the rest of the mode-dependent copy. */
export function generateMetadata(): Metadata {
  return {
    title: "Civilian keywords from your service record",
    description: COPY[serverConfig().mode].metaDescription,
  };
}

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
