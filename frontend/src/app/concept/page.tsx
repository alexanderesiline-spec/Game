"use client";

import {useState, useRef, useEffect} from "react";
import {useRouter} from "next/navigation";
import {Send, Sparkles, ArrowRight, BookOpen, Loader2} from "lucide-react";
import toast from "react-hot-toast";
import {conceptsApi, storiesApi, type StoryData} from "@/lib/api";
import {useAuthStore} from "@/lib/store";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const STARTER_IDEAS = [
  "A teenager discovers they can rewind time by 10 seconds, but every use ages them",
  "Two rival chefs in a fantasy world compete using magical ingredients",
  "A detective who can only see the last moment of a dead person's life",
  "An ordinary librarian finds a book that rewrites reality as they read it",
];

export default function ConceptPage() {
  const router = useRouter();
  const {token} = useAuthStore();
  const [phase, setPhase] = useState<"idea" | "chat" | "complete">("idea");
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [storyData, setStoryData] = useState<StoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState("manhwa");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({behavior: "smooth"});
  }, [messages]);

  const startSession = async (concept: string) => {
    if (!concept.trim()) return;
    setLoading(true);
    try {
      const res = await conceptsApi.start(concept);
      setSessionId(res.session_id);
      setMessages([
        {role: "user", content: concept},
        {role: "assistant", content: res.reply},
      ]);
      setPhase("chat");
      if (res.is_complete && res.story_data) {
        setStoryData(res.story_data);
        setPhase("complete");
      }
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !sessionId || loading) return;
    const msg = inputText.trim();
    setInputText("");
    setMessages((m) => [...m, {role: "user", content: msg}]);
    setLoading(true);
    try {
      const res = await conceptsApi.continue(sessionId, msg);
      setMessages((m) => [...m, {role: "assistant", content: res.reply}]);
      if (res.is_complete && res.story_data) {
        setStoryData(res.story_data);
        setPhase("complete");
      }
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const createComic = async () => {
    if (!storyData) return;
    setLoading(true);
    try {
      const story = await storiesApi.createFromConcept(
        storyData.title,
        storyData.prose_draft,
        selectedStyle
      );
      toast.success("Story created! Starting comic generation...");
      router.push(`/create?story_id=${story.id}&auto=true`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-8 py-5 border-b border-[#2e2e4a]">
        <a href="/" className="text-xl font-bold gradient-text">PanelForge</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400">Concept Generator</span>
      </div>

      <div className="flex-1 flex max-w-3xl mx-auto w-full px-4 py-8">
        {/* PHASE: IDEA INPUT */}
        {phase === "idea" && (
          <div className="w-full">
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-900/30 border border-purple-700/50 text-sm text-purple-300 mb-6">
                <Sparkles size={14} />
                Concept Generator
              </div>
              <h1 className="text-4xl font-extrabold mb-3">What&apos;s your story idea?</h1>
              <p className="text-gray-400">
                Doesn&apos;t need to be perfect — even one sentence works.
                I&apos;ll ask smart questions to develop it.
              </p>
            </div>

            <div className="bg-[#1a1a2e] rounded-2xl border border-[#2e2e4a] p-6 mb-6">
              <textarea
                className="w-full bg-transparent text-lg resize-none outline-none placeholder-gray-600 min-h-[120px]"
                placeholder="A story about..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    startSession(inputText);
                  }
                }}
                autoFocus
              />
              <div className="flex justify-between items-center pt-4 border-t border-[#2e2e4a]">
                <span className="text-xs text-gray-600">Ctrl+Enter to submit</span>
                <button
                  onClick={() => startSession(inputText)}
                  disabled={loading || !inputText.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 bg-[#7c3aed] hover:bg-[#6d28d9] disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-semibold transition"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                  Develop Concept
                </button>
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider">Need inspiration?</p>
              <div className="grid grid-cols-1 gap-2">
                {STARTER_IDEAS.map((idea, i) => (
                  <button
                    key={i}
                    onClick={() => setInputText(idea)}
                    className="text-left px-4 py-3 bg-[#1a1a2e] hover:bg-[#22223a] border border-[#2e2e4a] hover:border-purple-700/50 rounded-xl text-sm text-gray-300 transition"
                  >
                    &ldquo;{idea}&rdquo;
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* PHASE: CHAT */}
        {phase === "chat" && (
          <div className="w-full flex flex-col" style={{height: "calc(100vh - 180px)"}}>
            <div className="flex-1 overflow-y-auto space-y-4 pb-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[80%] px-5 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user" ? "chat-user" : "chat-ai"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="chat-ai px-5 py-3">
                    <Loader2 size={16} className="animate-spin text-purple-400" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="bg-[#1a1a2e] border border-[#2e2e4a] rounded-2xl p-4">
              <textarea
                ref={inputRef}
                className="w-full bg-transparent text-sm resize-none outline-none placeholder-gray-600 min-h-[60px] max-h-[160px]"
                placeholder="Reply..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                disabled={loading}
              />
              <div className="flex justify-between items-center pt-3 border-t border-[#2e2e4a]">
                <span className="text-xs text-gray-600">Enter to send · Shift+Enter for newline</span>
                <button
                  onClick={sendMessage}
                  disabled={loading || !inputText.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-[#7c3aed] hover:bg-[#6d28d9] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-semibold transition"
                >
                  <Send size={14} />
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* PHASE: COMPLETE */}
        {phase === "complete" && storyData && (
          <div className="w-full space-y-6">
            <div className="text-center">
              <div className="text-4xl mb-3">🎉</div>
              <h2 className="text-3xl font-bold mb-2">{storyData.title}</h2>
              <p className="text-gray-400 italic">&ldquo;{storyData.tagline}&rdquo;</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1a1a2e] rounded-xl border border-[#2e2e4a] p-4">
                <div className="text-xs text-purple-400 uppercase tracking-wider mb-2">Genre</div>
                <div className="flex flex-wrap gap-2">
                  {storyData.genre.map((g) => (
                    <span key={g} className="px-2 py-1 bg-purple-900/30 rounded-full text-xs text-purple-300">{g}</span>
                  ))}
                </div>
              </div>
              <div className="bg-[#1a1a2e] rounded-xl border border-[#2e2e4a] p-4">
                <div className="text-xs text-purple-400 uppercase tracking-wider mb-2">Tone</div>
                <div className="text-sm text-gray-300">{storyData.tone}</div>
              </div>
            </div>

            <div className="bg-[#1a1a2e] rounded-xl border border-[#2e2e4a] p-4">
              <div className="text-xs text-purple-400 uppercase tracking-wider mb-3">Characters</div>
              <div className="space-y-2">
                {storyData.characters.slice(0, 4).map((c) => (
                  <div key={c.name} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-purple-900/50 flex items-center justify-center text-xs font-bold text-purple-300 flex-shrink-0">
                      {c.name[0]}
                    </div>
                    <div>
                      <div className="font-semibold text-sm">{c.name} <span className="text-purple-400 text-xs">({c.role})</span></div>
                      <div className="text-xs text-gray-400">{c.motivation}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-[#1a1a2e] rounded-xl border border-[#2e2e4a] p-4">
              <div className="text-xs text-purple-400 uppercase tracking-wider mb-2">Story Preview</div>
              <p className="text-sm text-gray-300 leading-relaxed line-clamp-6">
                {storyData.prose_draft}
              </p>
            </div>

            {/* Style + Generate */}
            <div className="bg-[#1a1a2e] rounded-2xl border border-purple-700/50 p-6">
              <h3 className="font-bold mb-4">Choose your comic style</h3>
              <div className="grid grid-cols-3 gap-3 mb-6">
                {(["manga", "manhwa", "western"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSelectedStyle(s)}
                    className={`py-3 px-4 rounded-xl border text-sm font-semibold transition ${
                      selectedStyle === s
                        ? "bg-purple-600 border-purple-500 text-white"
                        : "bg-[#0d0d1a] border-[#2e2e4a] text-gray-300 hover:border-purple-700/50"
                    }`}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
              <button
                onClick={createComic}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 rounded-xl font-bold text-lg transition"
              >
                {loading ? (
                  <Loader2 size={20} className="animate-spin" />
                ) : (
                  <BookOpen size={20} />
                )}
                Generate My Comic
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
