import { MailWarning } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Nudge for an unconfirmed address. Hidden when the server has no mail
 * configured, since asking someone to check an inbox that will never receive
 * anything is worse than staying quiet.
 */
export default function VerifyBanner({ mailEnabled }: { mailEnabled: boolean }) {
  const { token, user } = useAuth();
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (!user || user.email_verified || !mailEnabled || dismissed) return null;

  const resend = async () => {
    setBusy(true);
    try {
      await api.resendVerification(token!);
      setSent(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-b border-amber/20 bg-amber/10 px-6 py-2.5 text-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
        <MailWarning size={16} className="text-amber" />
        <span className="text-snow/90">
          {sent ? `Sent — check ${user.email}.` : `Confirm your email address (${user.email}) to secure your account.`}
        </span>
        {!sent && (
          <button onClick={resend} disabled={busy} className="font-semibold text-amber underline disabled:opacity-60">
            {busy ? "Sending…" : "Resend link"}
          </button>
        )}
        <button onClick={() => setDismissed(true)} className="ml-auto text-fog hover:text-snow">Dismiss</button>
      </div>
    </div>
  );
}
