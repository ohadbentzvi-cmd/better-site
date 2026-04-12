/**
 * Admin layout — enforces HTTP basic auth on all /admin routes.
 *
 * The actual auth check happens in middleware.ts at the edge. This layout
 * exists so every admin page inherits the same chrome.
 */
export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <div className="admin-root">{children}</div>;
}
