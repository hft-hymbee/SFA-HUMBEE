import type { Metadata } from "next";
import "@humbee/design-tokens/css";
import { SessionBoundary } from "@/src/features/identity/session-boundary";
import { AppQueryProvider } from "@/src/shared/state";
import "./globals.css";

export const metadata: Metadata = {
  title: "Humbee GO",
  description: "Humbee sales force automation.",
};

const webShellScript = `(function(){var w=window;var native=(w.Capacitor&&w.Capacitor.isNativePlatform&&w.Capacitor.isNativePlatform())||w.androidBridge||location.protocol==="capacitor:";if(!native)document.documentElement.setAttribute("data-shell","web");})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: webShellScript }} />
      </head>
      <body>
        <AppQueryProvider>
          <SessionBoundary>{children}</SessionBoundary>
        </AppQueryProvider>
      </body>
    </html>
  );
}
