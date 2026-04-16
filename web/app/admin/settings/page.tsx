import { cookies } from "next/headers";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Divider } from "@/components/ui/divider";
import { PageHeader } from "@/components/ui/page-header";
import { ChangePasswordForm } from "@/components/admin/change-password-form";
import { CreateAnalystForm } from "@/components/admin/create-analyst-form";
import { SESSION_COOKIE_NAME, verifySession } from "@/lib/admin/session";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session) return null;

  return (
    <>
      <PageHeader title="Settings" />

      <div className="space-y-6 pb-12 max-w-xl">
        <Card>
          <CardHeader>Change password</CardHeader>
          <CardBody>
            <ChangePasswordForm />
          </CardBody>
        </Card>

        {session.is_superadmin ? (
          <>
            <Divider />
            <Card>
              <CardHeader>Create analyst</CardHeader>
              <CardBody>
                <p className="text-sm text-[var(--text-secondary)] mb-4">
                  New analysts can sign in immediately after creation.
                  Share their username and password securely.
                </p>
                <CreateAnalystForm />
              </CardBody>
            </Card>
          </>
        ) : null}
      </div>
    </>
  );
}
