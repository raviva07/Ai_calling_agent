import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Calling Agent",
  description: "AI-powered outbound calling agent administration dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">
              <div className="logo" aria-hidden="true">AI</div>
              <div><strong>AI Calling Agent</strong><span>Voice automation console</span></div>
            </div>
            <nav aria-label="Primary navigation">
              <Link href="/" className="navItem"><span>◫</span> Dashboard</Link>
              <a href="/#campaign" className="navItem"><span>＋</span> New campaign</a>
              <a href="/#calls" className="navItem"><span>☎</span> Call history</a>
            </nav>
            <div className="sidebarFooter">
              <div className="liveDot" /> AI Calling Agent ready
            </div>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
