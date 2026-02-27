import { Search, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useAppContext } from "../context/AppContext";
import { useNewsData } from "../hooks/useNewsData";

export function Header() {
  const { loading } = useAppContext();
  const { refreshNews } = useNewsData();
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const timeoutRef = { current: null as ReturnType<typeof setTimeout> | null };

  const fetchSuggestions = async (query: string) => {
    if (!query.trim()) { setSuggestions([]); setShowSuggestions(false); return; }
    try {
      const res = await fetch(`/api/suggest?q=${encodeURIComponent(query)}&type=list`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const data = await res.json();
        setSuggestions((data[1] as string[]).slice(0, 8));
        setShowSuggestions(true);
      }
    } catch { setSuggestions([]); }
  };

  const handleInput = (value: string) => {
    setSearchQuery(value);
    setActiveSuggestion(-1);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => fetchSuggestions(value), 200);
  };

  const openGoogle = (query: string) => {
    if (!query.trim()) return;
    window.open(`https://www.google.com/search?q=${encodeURIComponent(query.trim())}`, "_blank", "noopener,noreferrer");
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveSuggestion(p => Math.min(p + 1, suggestions.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveSuggestion(p => Math.max(p - 1, -1)); }
    else if (e.key === "Enter") openGoogle(activeSuggestion >= 0 ? suggestions[activeSuggestion] : searchQuery);
    else if (e.key === "Escape") setShowSuggestions(false);
  };

  return (
    <header className="bg-white border-b border-gray-100">
      <div className="px-8 h-16 flex items-center gap-6">

        {/* Search bar */}
        <div className="flex-1 max-w-md relative"
          onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setShowSuggestions(false); }}>
          <div className={`flex items-center gap-2.5 bg-gray-50 px-3.5 border border-gray-200 transition-all duration-150
            ${showSuggestions && suggestions.length > 0 ? "rounded-t-xl" : "rounded-xl"}`}>
            <Search size={15} className="text-gray-400 shrink-0" />
            <input
              type="text" value={searchQuery}
              onChange={e => handleInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
              placeholder="Search…"
              className="flex-1 bg-transparent border-none outline-none py-2 text-sm text-gray-800 placeholder:text-gray-400" />
            {searchQuery && (
              <button onClick={() => { setSearchQuery(""); setSuggestions([]); setShowSuggestions(false); }}
                className="text-gray-400 hover:text-gray-600 text-sm leading-none">✕</button>
            )}
          </div>

          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 bg-white rounded-b-xl shadow-lg border border-gray-200 border-t-0 z-50 overflow-hidden">
              {suggestions.map((s, i) => (
                <div key={s} onMouseDown={e => { e.preventDefault(); openGoogle(s); }}
                  onMouseEnter={() => setActiveSuggestion(i)}
                  className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer text-sm transition-colors
                    ${activeSuggestion === i ? "bg-gray-50" : "hover:bg-gray-50"}`}>
                  <Search size={12} className="text-gray-400 shrink-0" />
                  <span className="text-gray-700">{s}</span>
                  <span className="ml-auto text-[0.65rem] text-gray-400">↗</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Refresh */}
        <button onClick={refreshNews} disabled={loading}
          className={`ml-auto flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 transition-colors
            ${loading ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}>
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>
    </header>
  );
}
