import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Mark from "../components/Mark";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Landing page for the link in a confirmation email. Runs once on mount, and
 * refreshes the signed-in user so the "confirm your email" banner disappears.
 */
export default function Verify() {
  const [params] = useSearchParams();
  const { token: session, refresh } = useAuth();
  const [state, setState] = useState<"working" | "done" | "failed">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("failed");
      setMessage("That link is missing its token. Try copying the whole URL from the email.");
      return;
    }
    api.verifyEmail(token)
      .then(async () => {
        setState("done");
        if (session) await refresh();
      })
      .catch((e) => { setState("failed"); setMessage((e as Error).message); });
  }, []);

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center text-center">
      <Mark className="h-10 w-10" />
      {state === "working" && <p className="mt-6 text-fog">Confirming your email…</p>}
      {state === "done" && (
        <>
          <CheckCircle2 size={40} className="mt-6 text-mint" />
          <h1 className="mt-4 text-2xl font-bold">Email confirmed</h1>
          <p className="mt-2 text-fog">Thanks. Your account is all set.</p>
          <Link to="/" className="mt-6 rounded-lg bg-amber px-5 py-2.5 font-semibold text-ink">Go to PlayNext</Link>
        </>
      )}
      {state === "failed" && (
        <>
          <XCircle size={40} className="mt-6 text-coral" />
          <h1 className="mt-4 text-2xl font-bold">That link didn't work</h1>
          <p className="mt-2 text-fog">{message}</p>
          <Link to="/" className="mt-6 rounded-lg border border-line px-5 py-2.5 text-sm">Back to PlayNext</Link>
        </>
      )}
    </div>
  );
}
