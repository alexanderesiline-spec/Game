/**
 * Global auth + user state via Zustand.
 * Persists token in localStorage.
 */

import {create} from "zustand";
import {persist} from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: string | null;
  email: string | null;
  credits: number;
  setAuth: (token: string, userId: string, email: string, credits: number) => void;
  updateCredits: (credits: number) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      email: null,
      credits: 0,
      setAuth: (token, userId, email, credits) =>
        set({token, userId, email, credits}),
      updateCredits: (credits) => set({credits}),
      logout: () => set({token: null, userId: null, email: null, credits: 0}),
    }),
    {name: "panelforge-auth"}
  )
);
