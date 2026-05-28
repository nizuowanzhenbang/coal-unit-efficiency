import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  role: string | null;
  fullName: string | null;
  setAuth: (token: string, role: string, fullName: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      role: null,
      fullName: null,
      setAuth: (token, role, fullName) => set({ token, role, fullName }),
      logout: () => set({ token: null, role: null, fullName: null }),
    }),
    { name: "cue-auth" }
  )
);
