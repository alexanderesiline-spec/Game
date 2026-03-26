const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {"Content-Type": "application/json", ...options?.headers},
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({detail: res.statusText}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// ─── Concepts ────────────────────────────────────────────────────────────────

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
  get: (session_id: string) =>
    request<ConceptSession & {messages: Array<{role: string; content: string}>}>(`/api/concepts/${session_id}`),
};

// ─── Stories ─────────────────────────────────────────────────────────────────

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
  uploadFile: (formData: FormData) =>
    fetch(`${API_URL}/api/stories/upload`, {method: "POST", body: formData}).then(
      (r) => r.json() as Promise<Story>
    ),
  createFromConcept: (title: string, content: string, style: string) =>
    request<Story>(
      `/api/stories/from-concept?title=${encodeURIComponent(title)}&content=${encodeURIComponent(content)}&style=${style}`,
      {method: "POST"}
    ),
  list: () => request<Story[]>("/api/stories/"),
  get: (id: string) => request<Story & {content: string}>(`/api/stories/${id}`),
};

// ─── Comics ───────────────────────────────────────────────────────────────────

export interface ComicJob {
  id: string;
  story_id: string;
  title: string;
  style: string;
  status: string;
  progress: number;
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
  image?: {url: string; width: number; height: number};
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
