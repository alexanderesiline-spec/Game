"use client";

import {useState} from "react";
import {useRouter} from "next/navigation";
import Link from "next/link";
import {Loader2, Zap} from "lucide-react";
import toast from "react-hot-toast";
import {authApi} from "@/lib/api";
import {useAuthStore} from "@/lib/store";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    try {
      const res =
        tab === "login"
          ? await authApi.login(email, password)
          : await authApi.register(email, password);
      setAuth(res.access_token, res.user_id, res.email, res.credits);
      toast.success(tab === "login" ? "Welcome back!" : "Account created!");
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-extrabold gradient-text">
            PanelForge
          </Link>
          <p className="text-gray-400 mt-2 text-sm">
            {tab === "login" ? "Welcome back" : "Create your account"}
          </p>
        </div>

        <div className="bg-[#1a1a2e] border border-[#2e2e4a] rounded-2xl p-8">
          {/* Tab toggle */}
          <div className="flex bg-[#0d0d1a] rounded-xl p-1 mb-6">
            {(["login", "register"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2 text-sm font-semibold rounded-lg transition ${
                  tab === t ? "bg-[#7c3aed] text-white" : "text-gray-400 hover:text-white"
                }`}
              >
                {t === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-[#0d0d1a] border border-[#2e2e4a] focus:border-purple-500 rounded-xl px-4 py-3 text-sm outline-none transition"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={tab === "register" ? "Min 8 characters" : "••••••••"}
                className="w-full bg-[#0d0d1a] border border-[#2e2e4a] focus:border-purple-500 rounded-xl px-4 py-3 text-sm outline-none transition"
                required
                minLength={tab === "register" ? 8 : 1}
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 bg-[#7c3aed] hover:bg-[#6d28d9] disabled:opacity-50 rounded-xl font-semibold transition"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Zap size={16} />
              )}
              {tab === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-600 mt-4">
          By signing up you agree to our Terms of Service
        </p>
      </div>
    </div>
  );
}
