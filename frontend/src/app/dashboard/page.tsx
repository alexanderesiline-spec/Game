"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import Link from "next/link";
import {Plus, BookOpen, Coins, Loader2, LogOut, Sparkles, ChevronRight} from "lucide-react";
import toast from "react-hot-toast";
import {comicsApi, billingApi, type ComicJob, type Tier} from "@/lib/api";
import {useAuthStore} from "@/lib/store";

const STATUS_COLORS: Record<string, string> = {
  complete:   "text-green-400 bg-green-900/30",
  generating: "text-yellow-400 bg-yellow-900/30",
  assembling: "text-blue-400 bg-blue-900/30",
  parsing:    "text-purple-400 bg-purple-900/30",
  queued:     "text-gray-400 bg-gray-900/30",
  failed:     "text-red-400 bg-red-900/30",
};

export default function DashboardPage() {
  const router = useRouter();
  const {token, email, credits, updateCredits, logout} = useAuthStore();
  const [comics, setComics] = useState<ComicJob[]>([]);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loadingComics, setLoadingComics] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    Promise.all([
      comicsApi.list().then(setComics).catch(() => {}),
      billingApi.getTiers().then(setTiers).catch(() => {}),
    ]).finally(() => setLoadingComics(false));
  }, [token]);

  const buyCredits = async (tier: Tier) => {
    setCheckingOut(tier.id);
    try {
      const origin = window.location.origin;
      const res = await billingApi.createCheckout(
        tier.id,
        `${origin}/dashboard?success=1`,
        `${origin}/dashboard`,
      );
      window.location.href = res.checkout_url;
    } catch (err: any) {
      toast.error(err.message);
      setCheckingOut(null);
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-[#2e2e4a]">
        <Link href="/" className="text-xl font-bold gradient-text">PanelForge</Link>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1a1a2e] border border-[#2e2e4a] rounded-lg text-sm">
            <Coins size={14} className="text-yellow-400" />
            <span className="font-bold text-yellow-400">{credits}</span>
            <span className="text-gray-400">credits</span>
          </div>
          <span className="text-sm text-gray-500">{email}</span>
          <button onClick={handleLogout} className="text-gray-500 hover:text-white transition">
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-4">
          <Link
            href="/concept"
            className="group flex items-center gap-4 p-5 bg-gradient-to-br from-purple-900/40 to-pink-900/20 border border-purple-700/40 hover:border-purple-500 rounded-2xl transition"
          >
            <div className="w-12 h-12 rounded-xl bg-purple-600/30 flex items-center justify-center">
              <Sparkles size={24} className="text-purple-300" />
            </div>
            <div>
              <div className="font-bold">Generate Concept</div>
              <div className="text-sm text-gray-400">Start with an idea</div>
            </div>
            <ChevronRight size={16} className="ml-auto text-gray-600 group-hover:text-purple-400 transition" />
          </Link>
          <Link
            href="/create"
            className="group flex items-center gap-4 p-5 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-700/50 rounded-2xl transition"
          >
            <div className="w-12 h-12 rounded-xl bg-[#2e2e4a] flex items-center justify-center">
              <BookOpen size={24} className="text-gray-300" />
            </div>
            <div>
              <div className="font-bold">I have a story</div>
              <div className="text-sm text-gray-400">Upload or paste text</div>
            </div>
            <ChevronRight size={16} className="ml-auto text-gray-600 group-hover:text-purple-400 transition" />
          </Link>
        </div>

        {/* Credits / pricing */}
        {credits === 0 && (
          <div className="bg-yellow-900/20 border border-yellow-700/40 rounded-2xl p-5">
            <div className="font-semibold text-yellow-300 mb-1">You're out of credits</div>
            <div className="text-sm text-yellow-200/70 mb-4">Purchase credits to generate comics.</div>
            <div className="grid grid-cols-3 gap-3">
              {tiers.map((tier) => (
                <button
                  key={tier.id}
                  onClick={() => buyCredits(tier)}
                  disabled={!!checkingOut}
                  className="p-4 bg-[#1a1a2e] border border-yellow-700/30 hover:border-yellow-500 rounded-xl text-left transition disabled:opacity-50"
                >
                  <div className="font-bold text-lg">${tier.price_dollars}</div>
                  <div className="text-sm text-gray-300">{tier.credits} comics</div>
                  <div className="text-xs text-gray-500 mt-1">
                    ${(tier.price_dollars / tier.credits).toFixed(2)}/comic
                  </div>
                  {checkingOut === tier.id && (
                    <Loader2 size={12} className="animate-spin mt-1 text-yellow-400" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Comics list */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Your Comics</h2>
            {comics.length > 0 && (
              <Link
                href="/create"
                className="flex items-center gap-1.5 text-sm text-purple-400 hover:text-purple-300 transition"
              >
                <Plus size={14} /> New comic
              </Link>
            )}
          </div>

          {loadingComics ? (
            <div className="flex justify-center py-12">
              <Loader2 size={28} className="animate-spin text-purple-400" />
            </div>
          ) : comics.length === 0 ? (
            <div className="text-center py-16 bg-[#1a1a2e] rounded-2xl border border-[#2e2e4a]">
              <BookOpen size={40} className="mx-auto mb-3 text-gray-600" />
              <p className="text-gray-400 mb-4">No comics yet</p>
              <Link
                href={credits > 0 ? "/concept" : "#"}
                onClick={credits === 0 ? () => toast("Purchase credits first") : undefined}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#7c3aed] hover:bg-[#6d28d9] rounded-xl text-sm font-semibold transition"
              >
                <Sparkles size={15} /> Create your first comic
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {comics.map((comic) => (
                <Link
                  key={comic.id}
                  href={`/comics/${comic.id}`}
                  className="block p-5 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-700/50 rounded-2xl transition group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-bold group-hover:text-purple-300 transition truncate pr-2">
                      {comic.title}
                    </h3>
                    <span
                      className={`text-xs px-2 py-1 rounded-full font-medium flex-shrink-0 ${
                        STATUS_COLORS[comic.status] ?? "text-gray-400 bg-gray-900/30"
                      }`}
                    >
                      {comic.status}
                    </span>
                  </div>

                  <div className="flex gap-3 text-xs text-gray-500 mb-3">
                    <span className="capitalize">{comic.style}</span>
                    <span>·</span>
                    <span>{comic.page_count} pages</span>
                  </div>

                  {comic.status !== "complete" && comic.status !== "failed" && (
                    <div className="h-1.5 bg-[#0d0d1a] rounded-full overflow-hidden">
                      <div
                        className="h-full progress-shimmer rounded-full transition-all duration-500"
                        style={{width: `${comic.progress}%`}}
                      />
                    </div>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Buy more credits (if they have some but might want more) */}
        {credits > 0 && tiers.length > 0 && (
          <div>
            <h2 className="text-xl font-bold mb-4">Buy More Credits</h2>
            <div className="grid grid-cols-3 gap-4">
              {tiers.map((tier) => (
                <button
                  key={tier.id}
                  onClick={() => buyCredits(tier)}
                  disabled={!!checkingOut}
                  className="p-5 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-500 rounded-2xl text-left transition group disabled:opacity-50"
                >
                  <div className="text-2xl font-extrabold text-white mb-1">
                    ${tier.price_dollars}
                  </div>
                  <div className="font-semibold text-purple-300 mb-2">
                    {tier.credits} comics
                  </div>
                  <div className="text-xs text-gray-500">
                    ${(tier.price_dollars / tier.credits).toFixed(2)} per comic
                  </div>
                  {checkingOut === tier.id && (
                    <Loader2 size={14} className="animate-spin mt-2 text-purple-400" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
