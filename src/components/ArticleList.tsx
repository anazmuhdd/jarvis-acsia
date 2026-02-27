import { useNavigate } from "react-router-dom";
import { Newspaper, ChevronRight, Loader2, AlignLeft } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppContext } from "../context/AppContext";

export function ArticleList() {
  const navigate = useNavigate();
  const { news, loading, apiError, selectedArticle, setSelectedArticle } = useAppContext();

  return (
    <div className="flex flex-col h-full min-h-0 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <h2 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <Newspaper size={15} className="text-[#1a73e8]" /> Top Stories
        </h2>
        <button onClick={() => navigate("/articles")}
          className="flex items-center gap-1 text-xs text-[#1a73e8] hover:opacity-70 transition-opacity font-medium">
          View all <ChevronRight size={12} />
        </button>
      </div>

      {/* States */}
      {loading && news.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3">
          <Loader2 size={26} className="text-[#1a73e8] animate-spin" />
          <p className="text-xs text-gray-400">Loading…</p>
        </div>
      ) : apiError ? (
        <p className="text-xs text-red-500 text-center py-4">{apiError}</p>
      ) : news.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-2">
          <Newspaper size={28} className="text-gray-200" />
          <p className="text-xs text-gray-400">No stories yet</p>
        </div>
      ) : (
        /* Scrollable 2-col grid */
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="grid grid-cols-3 gap-5 content-start p-5">
            <AnimatePresence>
              {news.map((article, idx) => {
                const isActive = selectedArticle?.url === article.url;
                return (
                  <motion.button
                    key={article.url + idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, delay: Math.min(idx, 10) * 0.04 }}
                    onClick={() => setSelectedArticle(article)}
                    className={`w-full text-left flex flex-col rounded-xl overflow-hidden transition-all duration-200
                      ${isActive
                        ? "ring-1 ring-[#1a73e8] shadow-md"
                        : "hover:shadow-md"}`}>
                    {/* Thumbnail */}
                    {article.urlToImage ? (
                      <div className="overflow-hidden shrink-0 bg-gray-100">
                        <img src={article.urlToImage} alt="" className="w-full h-full object-cover" />
                      </div>
                    ) : (
                      <div className="h-28 bg-gray-50 flex items-center justify-center shrink-0">
                        <AlignLeft size={22} className="text-gray-200" />
                      </div>
                    )}
                    {/* Text */}
                    <div className={`p-3 flex flex-col flex-1 ${isActive ? "bg-[#e8f0fe]" : "bg-white"}`}>
                      <span className="text-[0.6rem] font-bold uppercase tracking-widest text-[#1a73e8] mb-1">
                        {article.source.name}
                      </span>
                      <p className="text-[0.82rem] font-semibold line-clamp-3 leading-snug text-gray-800">
                        {article.title}
                      </p>
                    </div>
                  </motion.button>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
