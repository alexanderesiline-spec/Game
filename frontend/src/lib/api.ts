const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("panelforge-auth");
    return raw ? JSON.parse(raw)?.state?.token ?? null : null;
  } catch {
    return null;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? {Authorization: `Bearer ${token}`} : {}),
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({detail: res.statusText}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  user_id: string;
  email: string;
  credits: number;
}

export const authApi = {
  register: (email: string, password: string) =>
    request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({email, password}),
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({email, password}),
    }),
  me: () =>
    request<{id: string; email: string; credits: number; created_at: string}>("/api/auth/me"),
};

// ─── Billing ──────────────────────────────────────────────────────────────────

export interface Tier {
  id: string;
  label: string;
  credits: number;
  price_cents: number;
  price_dollars: number;
}

export const billingApi = {
  getTiers: () => request<Tier[]>("/api/billing/tiers"),
  createCheckout: (tier: string, success_url: string, cancel_url: string) =>
    request<{checkout_url: string; session_id: string}>("/api/billing/checkout", {
      method: "POST",
      body: JSON.stringify({tier, success_url, cancel_url}),
    }),
  getBalance: () => request<{credits: number; user_id: string}>("/api/billing/balance"),
};

// ─── Concepts ─────────────────────────────────────────────────────────────────

export interface ConceptSession {
  session_id: string;
  reply: string;
  is_complete: boolean;
  story_data?: StoryData | null;
  message_count: number;
}

export interface StoryData {
  title: string;
  tagline: string;
  genre: string[];
  tone: string;
  setting: {world: string; era: string; key_locations: string[]};
  characters: Array<{name: string; role: string; description: string; motivation: string; arc: string}>;
  story_outline: Array<{chapter: number; title: string; summary: string; key_scenes: string[]; emotional_beat: string}>;
  themes: string[];
  prose_draft: string;
}

export const conceptsApi = {
  start: (concept: string) =>
    request<ConceptSession>("/api/concepts/start", {
      method: "POST",
      body: JSON.stringify({concept}),
    }),
  continue: (session_id: string, message: string) =>
    request<ConceptSession>("/api/concepts/continue", {
      method: "POST",
      body: JSON.stringify({session_id, message}),
    }),
};

// ─── Stories ──────────────────────────────────────────────────────────────────

export interface Story {
  id: string;
  title: string;
  content_preview: string;
  word_count: number;
  style: string;
  source_type: string;
}

export const storiesApi = {
  createFromText: (title: string, content: string, style: string) =>
    request<Story>("/api/stories/text", {
      method: "POST",
      body: JSON.stringify({title, content, style}),
    }),
  uploadFile: (formData: FormData) => {
    const token = getToken();
    return fetch(`${API_URL}/api/stories/upload`, {
      method: "POST",
      headers: token ? {Authorization: `Bearer ${token}`} : {},
      body: formData,
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({detail: r.statusText}));
        throw new Error(err.detail || "Upload failed");
      }
      return r.json() as Promise<Story>;
    });
  },
  createFromConcept: (title: string, content: string, style: string) =>
    request<Story>("/api/stories/from-concept", {
      method: "POST",
      body: JSON.stringify({title, content, style}),
    }),
  get: (id: string) =>
    request<Story & {content: string}>(`/api/stories/${id}`),
  list: () => request<Array<{id: string; title: string; style: string; word_count: number}>>("/api/stories/"),
};

// ─── Comics ───────────────────────────────────────────────────────────────────

export interface ComicJob {
  id: string;
  story_id: string;
  title: string;
  style: string;
  status: string;
  progress: number;
  status_message: string;
  page_count: number;
  error?: string | null;
}

export interface ComicPages {
  id: string;
  title: string;
  style: string;
  status: string;
  pages: PageData[];
  characters: CharacterData[];
  character_references: Record<string, string>;
  export_paths: Record<string, string>;
}

export interface PageData {
  page_number: number;
  layout: string;
  panels: PanelData[];
}

export interface PanelData {
  panel_number: number;
  size: string;
  scene_description: string;
  dialogue: Array<{speaker: string; text: string; bubble_style: string}>;
  sfx: string[];
  mood: string;
  image?: {url: string; width: number; height: number} | null;
  image_error?: string;
}

export interface CharacterData {
  name: string;
  role: string;
  image_prompt_base: string;
}

export const comicsApi = {
  generate: (story_id: string, title: string, style: string, quality = "standard") =>
    request<ComicJob>("/api/comics/generate", {
      method: "POST",
      body: JSON.stringify({story_id, title, style, quality}),
    }),
  get: (id: string) => request<ComicJob>(`/api/comics/${id}`),
  getPages: (id: string) => request<ComicPages>(`/api/comics/${id}/pages`),
  list: () => request<ComicJob[]>("/api/comics/"),
};

// ─── WebSocket ────────────────────────────────────────────────────────────────

export function connectComicWS(
  comicId: string,
  onMessage: (data: Record<string, unknown>) => void
): () => void {
  const wsUrl = API_URL.replace(/^http/, "ws") + `/api/comics/${comicId}/ws`;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch {}
  };
  ws.onerror = () => {/* silent — polling is fallback */};
  return () => ws.close();
}
