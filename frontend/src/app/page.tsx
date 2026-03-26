"use client";

import Link from "next/link";
import {BookOpen, Sparkles, Zap, Palette, Download, ArrowRight} from "lucide-react";

const STYLES = [
  {name: "Manga", desc: "B&W ink, screen tones, dramatic angles", emoji: "⚡"},
  {name: "Manhwa", desc: "Full color, clean lines, webtoon scroll", emoji: "🎨"},
  {name: "Western", desc: "Bold inks, dynamic panels, superhero style", emoji: "💥"},
];

const STEPS = [
  {icon: BookOpen, label: "Add your story", desc: "Paste text, upload a file, or use our concept generator"},
  {icon: Sparkles, label: "AI parses scenes", desc: "Claude breaks your story into panels with character sheets"},
  {icon: Palette, label: "Images generate", desc: "FLUX AI creates each panel with consistent characters"},
  {icon: Download, label: "Download your comic", desc: "Export as CBZ, PDF, or webtoon strip"},
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-[#2e2e4a]">
        <span className="text-2xl font-bold gradient-text">PanelForge</span>
        <div className="flex gap-4">
          <Link href="/concept" className="px-4 py-2 text-sm text-gray-300 hover:text-white transition">
            Concept Generator
          </Link>
          <Link href="/create" className="px-5 py-2 bg-[#7c3aed] hover:bg-[#6d28d9] rounded-lg text-sm font-semibold transition">
            Start Creating
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="text-center py-24 px-8 max-w-4xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#1a1a2e] border border-[#3d2f7e] text-sm text-purple-300 mb-8">
          <Zap size={14} />
          Powered by Claude + FLUX AI
        </div>
        <h1 className="text-6xl font-extrabold mb-6 leading-tight">
          Turn any story into a{" "}
          <span className="gradient-text">stunning comic</span>
        </h1>
        <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
          Manga, manhwa, or western comics — with consistent characters across every panel.
          No art skills required.
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link
            href="/concept"
            className="flex items-center gap-2 px-8 py-4 bg-[#7c3aed] hover:bg-[#6d28d9] rounded-xl font-semibold text-lg transition"
          >
            <Sparkles size={20} />
            Generate a Concept
          </Link>
          <Link
            href="/create"
            className="flex items-center gap-2 px-8 py-4 border border-[#3d2f7e] hover:border-[#7c3aed] rounded-xl font-semibold text-lg text-gray-200 transition"
          >
            I have a story <ArrowRight size={20} />
          </Link>
        </div>
      </section>

      {/* Style picker preview */}
      <section className="py-16 px-8 max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12">Three styles. One story.</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {STYLES.map((s) => (
            <div key={s.name} className="comic-panel bg-[#1a1a2e] rounded-2xl p-6 cursor-pointer relative overflow-hidden">
              <div className="text-4xl mb-3">{s.emoji}</div>
              <h3 className="text-xl font-bold mb-2">{s.name}</h3>
              <p className="text-gray-400 text-sm">{s.desc}</p>
              <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 to-transparent pointer-events-none" />
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 px-8 max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {STEPS.map((step, i) => (
            <div key={i} className="relative">
              <div className="bg-[#1a1a2e] border border-[#2e2e4a] rounded-2xl p-6">
                <div className="w-10 h-10 rounded-full bg-[#7c3aed]/20 flex items-center justify-center mb-4">
                  <step.icon size={20} className="text-purple-400" />
                </div>
                <div className="text-xs font-bold text-purple-500 mb-1">STEP {i + 1}</div>
                <h3 className="font-bold mb-2">{step.label}</h3>
                <p className="text-gray-400 text-sm">{step.desc}</p>
              </div>
              {i < STEPS.length - 1 && (
                <ArrowRight className="hidden md:block absolute top-8 -right-3 text-purple-800" size={20} />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-8 text-center border-t border-[#2e2e4a]">
        <h2 className="text-4xl font-bold mb-4">Ready to forge your comic?</h2>
        <p className="text-gray-400 mb-8">Start with an idea or bring your own story</p>
        <Link href="/concept" className="inline-flex items-center gap-2 px-10 py-5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 rounded-xl font-bold text-lg transition">
          <Sparkles size={22} />
          Start for Free
        </Link>
      </section>
    </div>
  );
}
