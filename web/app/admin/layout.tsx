import { cookies } from "next/headers";
import { Sidebar } from "@/components/admin/sidebar";
import { MobileBlock } from "@/components/admin/mobile-block";
import { SESSION_COOKIE_NAME, verifySession } from "@/lib/admin/session";

/**
 * Admin layout — desktop-only sidebar + content columns.
 *
 * Auth is enforced in web/middleware.ts at the edge. By the time this layout
 * renders, any non-login /admin/* route has a valid session. The login page
 * short-circuits its own rendering (it checks for a session-less case and
 * renders a centered card with no sidebar).
 */
export default async function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySession(token) : null;

  // The login page is under this layout too (route file structure). When no
  // session is present, render children plain — login provides its own chrome.
  if (!session) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen bg-[var(--surface-0)] text-[var(--text-primary)]">
      <MobileBlock />
      <Sidebar username={session.username} />
      <main className="flex-1 min-w-0 overflow-x-hidden">
        <div className="px-6">{children}</div>
      </main>
    </div>
  );
}
