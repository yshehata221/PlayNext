import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Mark from "../components/Mark";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/** Landing page for a password-reset link: set a new password, get signed in. */
export default function ResetPassword() {
  const [params] = useSearchParams();
  const { acceptToken } = useAuth();
  const nav = useNavigate();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    if (password !== confirm) { setError("Those two passwords don't match."); return; }
    setBusy(true);
    try {
      const { access_token } = await api.resetPassword(token, password);
      await acceptToken(access_token);   // straight in, no need to type it again
      nav("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-lg border border-line bg-field px-3 py-2 text-snow placeholder:text-fog/60";

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center">
      <Mark className="h-9 w-9" />
      <h1 className="mt-6 text-3xl font-bold tracking-tight">Choose a new password</h1>
      {!token ? (
        <p className="mt-3 text-coral">That link is missing its token. Request a new one from the sign-in page.</p>
      ) : (
        <div className="mt-6 space-y-3">
          <input className={field} type="password" placeholder="New password (8+ characters)"
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <input className={field} type="password" placeholder="Repeat it" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
          {error && <p className="text-sm text-coral">{error}</p>}
          <button onClick={submit} disabled={busy || password.length < 8}
            className="w-full rounded-lg bg-amber py-2.5 font-semibold text-ink disabled:opacity-50">
            {busy ? "Saving…" : "Save and sign in"}
          </button>
        </div>
      )}
    </div>
  );
}
