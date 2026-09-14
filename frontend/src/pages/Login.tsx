import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"in" | "up" | "forgot">("in");
  const [forgotSent, setForgotSent] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [handle, setHandle] = useState<{ available: boolean; reason: string | null } | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === "forgot") {
        await api.forgotPassword(email);
        setForgotSent(true);
      } else if (mode === "in") {
        await signIn(email, password);
      } else {
        await signUp(email, name, username, password);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-lg border border-line bg-field px-3 py-2 text-snow placeholder:text-fog/60";

  // check the handle as they type, so nobody finds out it's taken after submitting
  useEffect(() => {
    if (mode !== "up" || username.length < 3) { setHandle(null); return; }
    const id = setTimeout(() => api.usernameAvailable(username).then(setHandle).catch(() => setHandle(null)), 350);
    return () => clearTimeout(id);
  }, [username, mode]);

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-5">
      <h1 className="text-5xl font-extrabold tracking-tight">PlayNext</h1>
      <p className="mt-2 text-lg text-fog">Stop scrolling. Start playing.</p>

      <div className="mt-10 space-y-3">
        {mode === "up" && (
          <>
            <input className={field} placeholder="What should we call you?" value={name} onChange={(e) => setName(e.target.value)} />
            <div>
              {/* the ring lives on the wrapper, so the inner input doesn't draw a
                  second one inside the border */}
              <div className="flex items-center rounded-lg border border-line bg-field px-3 focus-within:border-amber">
                <span className="text-fog">@</span>
                <input className="w-full bg-transparent px-1 py-2 text-snow outline-none focus-visible:outline-none placeholder:text-fog/60"
                  placeholder="username friends can add" value={username}
                  onChange={(e) => setUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))} maxLength={20} />
              </div>
              {handle && (
                <p className={`mt-1 text-xs ${handle.available ? "text-mint" : "text-coral"}`}>
                  {handle.available ? `@${username.toLowerCase()} is free` : handle.reason}
                </p>
              )}
            </div>
          </>
        )}
        <input className={field} type="email" placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => e.key === "Enter" && mode === "forgot" && submit()} />
        {mode !== "forgot" && (
          <input className={field} type="password" placeholder="Password (8+ characters)" value={password}
            onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
        )}
        {error && <p className="text-sm text-coral">{error}</p>}
        {forgotSent && (
          <p className="rounded-lg bg-panel px-3 py-2 text-sm text-mint">
            If an account exists for {email}, a reset link is on its way. It's good for an hour.
          </p>
        )}
        <button onClick={submit} disabled={busy || (mode === "up" && (!username || handle?.available === false))}
          className="w-full rounded-lg bg-amber py-2 font-semibold text-ink hover:brightness-110 disabled:opacity-50">
          {busy ? "…" : mode === "in" ? "Sign in" : mode === "up" ? "Create account" : "Send reset link"}
        </button>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <button className="text-fog hover:text-snow" onClick={() => { setMode(mode === "up" ? "in" : "up"); setError(null); setForgotSent(false); }}>
          {mode === "up" ? "Already have an account? Sign in" : "New here? Create an account"}
        </button>
        {mode !== "forgot" && (
          <button className="text-fog hover:text-snow" onClick={() => { setMode("forgot"); setError(null); }}>
            Forgot your password?
          </button>
        )}
        {mode === "forgot" && (
          <button className="text-fog hover:text-snow" onClick={() => { setMode("in"); setForgotSent(false); }}>
            Back to sign in
          </button>
        )}
      </div>
    </div>
  );
}
