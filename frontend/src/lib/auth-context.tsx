"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { setAccessToken, apiFetch } from "./api";

interface User {
  id: string;
  email: string;
  display_name: string | null;
  billing_mode: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (accessToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/auth/me");
      if (resp.ok) {
        const data = await resp.json();
        setUser(data);
        return true;
      }
    } catch {
      // ignore
    }
    return false;
  }, []);

  const login = useCallback(
    async (accessToken: string) => {
      setAccessToken(accessToken);
      await fetchUser();
    },
    [fetchUser]
  );

  const logout = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  // Silent refresh on mount
  useEffect(() => {
    async function tryRestore() {
      const API_URL =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      try {
        const resp = await fetch(`${API_URL}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (resp.ok) {
          const data = await resp.json();
          setAccessToken(data.access_token);
          await fetchUser();
        }
      } catch {
        // No valid session
      } finally {
        setIsLoading(false);
      }
    }
    tryRestore();
  }, [fetchUser]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
