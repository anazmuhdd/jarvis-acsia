import { ArrowLeft, ExternalLink } from "lucide-react";
import { useAppContext } from "../context/AppContext";

function cleanDesc(text: string): string {
  if (!text) return "";
  return text
    .replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">").replace(/&quot;/gi, '"').replace(/&#39;/gi, "'")
    .replace(/&[a-z]+;/gi, " ").replace(/\s+/g, " ").trim();
}

export function ArticleDetailPanel() {
  const { selectedArticle, setSelectedArticle } = useAppContext();
  if (!selectedArticle) return null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Back link */}
      <button onClick={() => setSelectedArticle(null)}
        className="flex items-center gap-1.5 text-xs text-[#1a73e8] font-medium hover:opacity-70 transition-opacity mb-4 shrink-0 w-fit">
        <ArrowLeft size={13} /> Back to Tasks
      </button>

      <div className="overflow-y-auto flex-1 min-h-0">
        {/* Hero image */}
        {selectedArticle.urlToImage && (
          <div className="w-full h-52 overflow-hidden rounded-xl mb-4 shrink-0">
            <img src={selectedArticle.urlToImage} alt={selectedArticle.title}
              className="w-full h-full object-cover" />
          </div>
        )}

        <span className="inline-block text-[0.6rem] font-bold uppercase tracking-widest text-[#1a73e8]
                         bg-[#e8f0fe] px-2 py-0.5 rounded-full mb-3">
          {selectedArticle.source.name}
        </span>
        <h1 className="text-lg font-bold text-gray-900 leading-snug mb-3">
          {selectedArticle.title}
        </h1>
        <p className="text-sm text-gray-500 leading-relaxed mb-5">
          {cleanDesc(selectedArticle.description)}
        </p>
        <a href={selectedArticle.url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-2 bg-[#1a73e8] hover:bg-[#1557b0] text-white text-xs font-semibold
                     px-4 py-2 rounded-lg transition-colors">
          Read Full Article <ExternalLink size={12} />
        </a>
      </div>
    </div>
  );
}
