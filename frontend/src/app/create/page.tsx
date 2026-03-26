"use client";

import {useState, useCallback, useEffect, Suspense} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {useDropzone} from "react-dropzone";
import {Upload, FileText, Type, Loader2, Zap, BookOpen} from "lucide-react";
import toast from "react-hot-toast";
import {storiesApi, comicsApi} from "@/lib/api";
import {useAuthStore} from "@/lib/store";
import Link from "next/link";

type InputMode = "text" | "upload";

function CreatePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {token} = useAuthStore();
  const [mode, setMode] = useState<InputMode>("text");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [style, setStyle] = useState("manhwa");
  const [quality, setQuality] = useState("standard");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token]);

  // Auto-generate if coming from concept page
  useEffect(() => {
    const storyId = searchParams.get("story_id");
    const auto = searchParams.get("auto");
    if (storyId && auto === "true") {
      handleGenerateFromId(storyId);
    }
  }, []);

  const handleGenerateFromId = async (storyId: string) => {
    try {
      const story = await storiesApi.get(storyId);
      setLoading(true);
      const comic = await comicsApi.generate(storyId, story.title, story.style, "standard");
      router.push(`/comics/${comic.id}`);
    } catch (e: any) {
      toast.error(e.message);
      setLoading(false);
    }
  };

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) {
      setFile(accepted[0]);
      if (!title) setTitle(accepted[0].name.replace(/\.[^/.]+$/, ""));
    }
  }, [title]);

  const {getRootProps, getInputProps, isDragActive} = useDropzone({
    onDrop,
    accept: {
      "text/plain": [".txt"],
      "application/pdf": [".pdf"],
      "application/epub+zip": [".epub"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const handleGenerate = async () => {
    if (!title.trim()) {
      toast.error("Please enter a title");
      return;
    }

    setLoading(true);
    try {
      let story;

      if (mode === "upload" && file) {
        const formData = new FormData();
        formData.append("title", title);
        formData.append("style", style);
        formData.append("file", file);
        story = await storiesApi.uploadFile(formData);
      } else {
        if (!content.trim()) {
          toast.error("Please enter your story");
          setLoading(false);
          return;
        }
        story = await storiesApi.createFromText(title, content, style);
      }

      const comic = await comicsApi.generate(story.id, title, style, quality);
      toast.success("Generation started!");
      router.push(`/comics/${comic.id}`);
    } catch (e: any) {
      toast.error(e.message);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full border-4 border-purple-500 border-t-transparent animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Creating your story...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="flex items-center gap-3 px-8 py-5 border-b border-[#2e2e4a]">
        <a href="/" className="text-xl font-bold gradient-text">PanelForge</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400">Create Comic</span>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Create your comic</h1>
          <p className="text-gray-400">
            Paste your story, upload a file, or{" "}
            <Link href="/concept" className="text-purple-400 hover:text-purple-300 underline">
              generate a concept first
            </Link>
          </p>
        </div>

        {/* Input mode toggle */}
        <div className="flex gap-2 mb-6 bg-[#1a1a2e] p-1.5 rounded-xl w-fit">
          {([["text", "Write / Paste", Type], ["upload", "Upload File", Upload]] as const).map(
            ([m, label, Icon]) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                  mode === m ? "bg-[#7c3aed] text-white" : "text-gray-400 hover:text-white"
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            )
          )}
        </div>

        <div className="space-y-5">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My Amazing Story"
              className="w-full bg-[#1a1a2e] border border-[#2e2e4a] focus:border-purple-500 rounded-xl px-4 py-3 text-sm outline-none transition"
            />
          </div>

          {/* Content area */}
          {mode === "text" ? (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Story Content
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Paste or type your story here. The more detail, the better the comic..."
                className="w-full bg-[#1a1a2e] border border-[#2e2e4a] focus:border-purple-500 rounded-xl px-4 py-3 text-sm outline-none transition resize-none min-h-[280px]"
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-600">
                  {content.split(/\s+/).filter(Boolean).length} words
                </span>
                <span className="text-xs text-gray-600">
                  Recommended: 200–5000 words
                </span>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Upload File
              </label>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition ${
                  isDragActive
                    ? "border-purple-500 bg-purple-900/20"
                    : file
                    ? "border-green-500 bg-green-900/10"
                    : "border-[#2e2e4a] hover:border-purple-700/50"
                }`}
              >
                <input {...getInputProps()} />
                {file ? (
                  <>
                    <FileText size={36} className="mx-auto mb-3 text-green-400" />
                    <p className="font-medium text-green-300">{file.name}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {(file.size / 1024).toFixed(0)} KB
                    </p>
                  </>
                ) : (
                  <>
                    <Upload size={36} className="mx-auto mb-3 text-gray-500" />
                    <p className="text-gray-300 font-medium">
                      {isDragActive ? "Drop it here" : "Drag & drop or click to upload"}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">TXT, PDF, EPUB — max 50MB</p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Style + Quality */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Comic Style</label>
              <div className="grid grid-cols-3 gap-2">
                {(["manga", "manhwa", "western"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStyle(s)}
                    className={`py-2 px-3 rounded-lg border text-xs font-semibold transition ${
                      style === s
                        ? "bg-purple-600 border-purple-500 text-white"
                        : "bg-[#1a1a2e] border-[#2e2e4a] text-gray-400 hover:border-purple-700/50"
                    }`}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Quality</label>
              <div className="grid grid-cols-2 gap-2">
                {(["standard", "high"] as const).map((q) => (
                  <button
                    key={q}
                    onClick={() => setQuality(q)}
                    className={`py-2 px-3 rounded-lg border text-xs font-semibold transition ${
                      quality === q
                        ? "bg-purple-600 border-purple-500 text-white"
                        : "bg-[#1a1a2e] border-[#2e2e4a] text-gray-400 hover:border-purple-700/50"
                    }`}
                  >
                    {q === "high" ? "⚡ High" : "Standard"}
                  </button>
                ))}
              </div>
              {quality === "high" && (
                <p className="text-xs text-yellow-400 mt-1">
                  Slower but better quality (uses FLUX-dev)
                </p>
              )}
            </div>
          </div>

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={loading || (!content.trim() && !file) || !title.trim()}
            className="w-full flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold text-lg transition"
          >
            {loading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Zap size={20} />
            )}
            Generate Comic
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CreatePage() {
  return (
    <Suspense>
      <CreatePageInner />
    </Suspense>
  );
}
