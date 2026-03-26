"use client";

import {useEffect, useState, useRef} from "react";
import {useParams, useRouter} from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {Download, Loader2, CheckCircle, XCircle, ChevronLeft, ChevronRight, Users, Coins} from "lucide-react";
import toast from "react-hot-toast";
import {comicsApi, connectComicWS, type ComicJob, type ComicPages, type PanelData} from "@/lib/api";
import {useAuthStore} from "@/lib/store";

const STATUS_STEPS = [
  {key: "queued",     label: "Queued"},
  {key: "parsing",   label: "Parsing story"},
  {key: "generating",label: "Generating panels"},
  {key: "assembling",label: "Assembling pages"},
  {key: "complete",  label: "Complete"},
];

const STYLE_LABELS: Record<string, string> = {
  manga:   "Manga (B&W)",
  manhwa:  "Manhwa (Color)",
  western: "Western Comic",
};

export default function ComicPage() {
  const {id} = useParams() as {id: string};
  const router = useRouter();
  const {token, credits} = useAuthStore();
  const [job, setJob] = useState<ComicJob | null>(null);
  const [pages, setPages] = useState<ComicPages | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const loadPages = async () => {
    try {
      const pageData = await comicsApi.getPages(id);
      setPages(pageData);
    } catch {
      // pages not ready yet — silently ignore
    }
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // Fallback polling (used if WebSocket fails to connect)
  const startPolling = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const data = await comicsApi.get(id);
        setJob(data);
        if (data.status === "complete") {
          stopPolling();
          await loadPages();
        } else if (data.status === "failed") {
          stopPolling();
          toast.error("Generation failed: " + (data.error ?? "unknown error"));
        }
      } catch {/* silent */}
    }, 4000);
  };

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }

    // Initial fetch to get current state immediately
    comicsApi.get(id).then(async (data) => {
      setJob(data);
      setLoading(false);
      if (data.status === "complete") {
        await loadPages();
        return; // No need for WS or polling
      }
      if (data.status === "failed") {
        toast.error("Generation failed: " + (data.error ?? "unknown error"));
        return;
      }

      // Comic still in progress — connect WebSocket for live updates
      const cleanup = connectComicWS(id, async (msg) => {
        const {type, status, progress, status_message, error} = msg as any;

        if (type === "progress" || type === "complete" || type === "error") {
          setJob((prev) =>
            prev
              ? {...prev, status: status ?? prev.status, progress: progress ?? prev.progress, status_message: status_message ?? prev.status_message}
              : prev
          );
        }

        if (status === "complete") {
          stopPolling();
          await loadPages();
        } else if (status === "failed") {
          stopPolling();
          toast.error("Generation failed: " + (error ?? "unknown error"));
        }
      });

      wsCleanupRef.current = cleanup;

      // Start polling as fallback — WS updates will keep it irrelevant,
      // but if WS dies the polling will catch terminal states
      startPolling();
    }).catch((err) => {
      toast.error(err.message);
      setLoading(false);
    });

    return () => {
      if (wsCleanupRef.current) wsCleanupRef.current();
      stopPolling();
    };
  }, [id, token]);

  const currentStepIndex = STATUS_STEPS.findIndex((s) => s.key === job?.status);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={40} className="animate-spin text-purple-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-[#2e2e4a]">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-xl font-bold gradient-text">PanelForge</Link>
          <span className="text-gray-600">/</span>
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300 text-sm transition">Dashboard</Link>
          <span className="text-gray-600">/</span>
          <span className="text-gray-400 truncate max-w-[200px]">{job?.title}</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1a1a2e] border border-[#2e2e4a] rounded-lg text-sm">
            <Coins size={14} className="text-yellow-400" />
            <span className="font-bold text-yellow-400">{credits}</span>
            <span className="text-gray-400">credits</span>
          </div>
          {pages && (
            <div className="flex gap-2">
              {pages.export_paths?.cbz && (
                <a
                  href={`/files/comics/${id}.cbz`}
                  download
                  className="flex items-center gap-2 px-4 py-2 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-500 rounded-lg text-sm transition"
                >
                  <Download size={15} /> CBZ
                </a>
              )}
              {pages.export_paths?.webp_strip && (
                <a
                  href={`/files/comics/${id}_strip.webp`}
                  download
                  className="flex items-center gap-2 px-4 py-2 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-500 rounded-lg text-sm transition"
                >
                  <Download size={15} /> Webtoon Strip
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Progress / status steps (shown while not complete) */}
        {job?.status !== "complete" && (
          <div className="mb-10">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-300">
                {job?.status === "failed"
                  ? "Generation Failed"
                  : job?.status_message || "Generating your comic…"}
              </h2>
              {job?.status !== "failed" && (
                <span className="text-sm text-purple-400 font-bold">{job?.progress ?? 0}%</span>
              )}
            </div>

            {job?.status !== "failed" && (
              <div className="h-2 bg-[#1a1a2e] rounded-full overflow-hidden mb-6">
                <div
                  className="h-full progress-shimmer rounded-full transition-all duration-500"
                  style={{width: `${job?.progress ?? 0}%`}}
                />
              </div>
            )}

            {job?.status === "failed" && (
              <div className="flex items-center gap-2 text-red-400 text-sm mb-4">
                <XCircle size={16} />
                {job.error ?? "An unexpected error occurred."}
              </div>
            )}

            {job?.status !== "failed" && (
              <div className="flex gap-2">
                {STATUS_STEPS.map((step, i) => (
                  <div
                    key={step.key}
                    className={`flex-1 flex flex-col items-center gap-1.5 ${
                      i < currentStepIndex
                        ? "text-green-400"
                        : i === currentStepIndex
                        ? "text-purple-400"
                        : "text-gray-600"
                    }`}
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs border-2 transition ${
                        i < currentStepIndex
                          ? "bg-green-900/50 border-green-500"
                          : i === currentStepIndex
                          ? "bg-purple-900/50 border-purple-500 animate-pulse"
                          : "bg-[#1a1a2e] border-[#2e2e4a]"
                      }`}
                    >
                      {i < currentStepIndex ? (
                        <CheckCircle size={14} />
                      ) : i === currentStepIndex ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <span>{i + 1}</span>
                      )}
                    </div>
                    <span className="text-[10px] text-center leading-tight">{step.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Comic viewer (shown when complete) */}
        {pages && (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold">{pages.title}</h1>
                <span className="text-sm text-purple-400">{STYLE_LABELS[pages.style] ?? pages.style}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span>{pages.pages.length} pages</span>
                <span>·</span>
                <span>{pages.pages.reduce((a, p) => a + p.panels.length, 0)} panels</span>
              </div>
            </div>

            {/* Characters */}
            {pages.characters.length > 0 && (
              <div className="bg-[#1a1a2e] rounded-xl border border-[#2e2e4a] p-4 mb-6">
                <div className="flex items-center gap-2 text-xs text-purple-400 uppercase tracking-wider mb-3">
                  <Users size={12} />
                  Characters
                </div>
                <div className="flex gap-4 flex-wrap">
                  {pages.characters.map((c) => (
                    <div key={c.name} className="flex items-center gap-2">
                      {pages.character_references?.[c.name] ? (
                        <img
                          src={pages.character_references[c.name]}
                          alt={c.name}
                          className="w-8 h-8 rounded-full object-cover"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-purple-900/50 flex items-center justify-center text-xs font-bold text-purple-300">
                          {c.name[0]}
                        </div>
                      )}
                      <div>
                        <div className="text-sm font-medium">{c.name}</div>
                        <div className="text-xs text-gray-500">{c.role}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Page navigation */}
            {pages.pages.length > 1 && (
              <div className="flex items-center justify-between mb-4">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                  className="flex items-center gap-1 px-3 py-2 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-500 disabled:opacity-30 rounded-lg text-sm transition"
                >
                  <ChevronLeft size={16} /> Previous
                </button>
                <span className="text-sm text-gray-400">
                  Page {currentPage + 1} of {pages.pages.length}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(pages.pages.length - 1, p + 1))}
                  disabled={currentPage === pages.pages.length - 1}
                  className="flex items-center gap-1 px-3 py-2 bg-[#1a1a2e] border border-[#2e2e4a] hover:border-purple-500 disabled:opacity-30 rounded-lg text-sm transition"
                >
                  Next <ChevronRight size={16} />
                </button>
              </div>
            )}

            {/* Panel grid */}
            {pages.pages[currentPage] && (
              <PanelGrid page={pages.pages[currentPage]} style={pages.style} />
            )}

            {/* Page dots */}
            {pages.pages.length > 1 && (
              <div className="flex gap-1.5 justify-center mt-6">
                {pages.pages.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setCurrentPage(i)}
                    className={`h-2 rounded-full transition-all ${
                      i === currentPage ? "bg-purple-500 w-5" : "bg-[#2e2e4a] w-2"
                    }`}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function PanelGrid({page, style}: {page: any; style: string}) {
  const panels: PanelData[] = page.panels ?? [];

  return (
    <div
      className={`gap-2 ${
        style === "manhwa" ? "flex flex-col" : "grid grid-cols-2 md:grid-cols-3"
      }`}
    >
      {panels.map((panel, i) => (
        <div
          key={i}
          className={`comic-panel relative overflow-hidden rounded-lg bg-[#1a1a2e] ${
            panel.size === "splash" ? "col-span-full" : ""
          }`}
          style={{
            aspectRatio:
              style === "manhwa" ? "16/9" : panel.size === "splash" ? "4/3" : "3/4",
          }}
        >
          {panel.image?.url ? (
            <Image
              src={panel.image.url}
              alt={panel.scene_description || `Panel ${i + 1}`}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 50vw"
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-600 p-4 gap-2">
              {panel.image_error ? (
                <XCircle size={16} className="text-red-700" />
              ) : (
                <Loader2 size={16} className="animate-spin text-purple-700" />
              )}
              <div className="text-xs text-center">{panel.scene_description}</div>
            </div>
          )}

          {/* Mood badge */}
          {panel.mood && (
            <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/70 rounded text-[10px] text-purple-300">
              {panel.mood}
            </div>
          )}

          {/* Dialogue overlay */}
          {panel.dialogue?.length > 0 && (
            <div className="absolute bottom-2 left-2 right-2">
              {panel.dialogue.slice(0, 2).map((d: any, j: number) => (
                <div
                  key={j}
                  className="mb-1 px-2 py-1 bg-white/90 text-black rounded text-[10px] font-medium leading-tight"
                >
                  <span className="text-purple-700 font-bold">{d.speaker}: </span>
                  {d.text}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
