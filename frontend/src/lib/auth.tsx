import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

interface User { id: number; email: string; display_name: string; username: string | null; steam_id: string | null; email_verified: boolean }

interface AuthCtx {
  token: string | null;
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, name: string, username: string, password: string) => Promise<void>;
  signOut: () => void;
  /** re-read the current user, e.g. after confirming an email address */
  refresh: () => Promise<void>;
  acceptToken: (token: string) => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null!);
const KEY = "playnext.token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!token);

  // on load, check the stored token still works
  useEffect(() => {
    if (!token) return;
    api.me(token)
      .then(setUser)
      .catch(() => { localStorage.removeItem(KEY); setToken(null); })
      .finally(() => setLoading(false));
  }, [token]);

  const accept = async (t: string) => {
    localStorage.setItem(KEY, t);
    setToken(t);
    setLoading(true);
  };

  return (
    <Ctx.Provider
      value={{
        token, user, loading,
        signIn: async (e, p) => accept((await api.login(e, p)).access_token),
        signUp: async (e, n, u, p) => accept((await api.register(e, n, u, p)).access_token),
        signOut: () => { localStorage.removeItem(KEY); setToken(null); setUser(null); },
        refresh: async () => { if (token) setUser(await api.me(token)); },
        acceptToken: accept,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
