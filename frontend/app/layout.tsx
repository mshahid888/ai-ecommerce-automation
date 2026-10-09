import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI E-Commerce Automation – Muster-Shop GmbH",
  description:
    "Demo des KI-Kundenservice für die Muster-Shop GmbH: Bestellstatus, Produktfragen und Retouren-Triage.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de" className="h-full">
      <body className="flex min-h-full flex-col bg-slate-50 font-sans text-slate-900 antialiased">
        <header className="bg-slate-900">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <div>
              <p className="text-lg font-semibold tracking-tight text-white">
                AI E-Commerce Automation
              </p>
              <p className="text-sm text-slate-400">
                Demo-Shop: Muster-Shop GmbH
              </p>
            </div>
            <Nav />
          </div>
        </header>

        <div
          role="note"
          aria-label="Demo-Hinweis"
          className="border-b border-amber-300 bg-amber-100"
        >
          <p className="mx-auto max-w-6xl px-4 py-2.5 text-sm font-medium text-amber-900 sm:px-6">
            Demo-Umgebung – simulierte Daten. Keine echten Bestellungen.
          </p>
        </div>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white">
          <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-slate-500 sm:px-6">
            Phase 1 – Demo-Skelett. Alle Daten sind simuliert; es werden keine
            echten Bestellungen verarbeitet.
          </p>
        </footer>
      </body>
    </html>
  );
}
