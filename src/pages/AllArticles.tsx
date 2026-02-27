import { useNavigate } from "react-router-dom";
import { ArrowLeft, ChevronRight, Newspaper, AlignLeft, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useAppContext } from "../context/AppContext";

function cleanDesc(text: string): string {
  if (!text) return "";
  return text
    .replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">").replace(/&quot;/gi, '"').replace(/&#39;/gi, "'")
    .replace(/&[a-z]+;/gi, " ").replace(/\s+/g, " ").trim();
}

export function AllArticles() {
  const navigate = useNavigate();
  const { news, loading } = useAppContext();

  return (
    <div className="min-h-screen bg-[#f4f4f5] font-sans">
      <div className=" mx-auto px-6 py-8">
        {/* Top bar */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-[#1a73e8] font-semibold text-sm hover:opacity-75 transition-opacity">
            <ArrowLeft size={17} /> Back
          </button>
          <div className="w-px h-5 bg-gray-200" />
          <h1 className="text-xl font-extrabold tracking-tight text-gray-900 flex items-center gap-2">
            <Newspaper size={20} className="text-[#1a73e8]" /> All Articles
          </h1>
          <span className="ml-auto text-xs text-gray-400 font-medium">
            {news.length} stories
          </span>
        </div>

        {/* Content */}
        {loading && news.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <Loader2 size={36} className="text-[#1a73e8] animate-spin" />
            <p className="text-gray-500 text-sm">Fetching latest stories…</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            <AnimatePresence mode="popLayout">
              {news.map((article, idx) => (
                <motion.a
                  key={article.url + idx}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  transition={{ duration: 0.3, delay: Math.min(idx, 16) * 0.035 }}
                  className="flex flex-col bg-white rounded-2xl border border-gray-100
                             shadow-[0_1px_3px_rgba(0,0,0,0.06)] overflow-hidden
                             hover:shadow-[0_6px_20px_rgba(0,0,0,0.1)] hover:-translate-y-0.5
                             transition-all duration-200 cursor-pointer no-underline text-inherit">
                  {/* Thumbnail */}
                  {article.urlToImage ? (
                    <div className="h-44 overflow-hidden">
                      <img
                        src={article.urlToImage}
                        alt={article.title}
                        className="w-full h-full object-cover hover:scale-105 transition-transform duration-300" />
                    </div>
                  ) : (
                    <div className="h-44 bg-gray-50 flex items-center justify-center">
                      <AlignLeft size={28} className="text-gray-200" />
                    </div>
                  )}

                  {/* Card body */}
                  <div className="p-4 flex flex-col flex-1">
                    <span className="text-[0.6rem] font-bold uppercase tracking-widest text-[#1a73e8] mb-1.5">
                      {article.source.name}
                    </span>
                    <h3 className="text-sm font-bold text-gray-900 leading-snug line-clamp-3 mb-2 flex-1">
                      {article.title}
                    </h3>
                    <p className="text-xs text-gray-500 line-clamp-2 mb-3">
                      {cleanDesc(article.description)}
                    </p>
                    <div className="flex items-center justify-end mt-auto">
                      <ChevronRight size={14} className="text-[#1a73e8]" />
                    </div>
                  </div>
                </motion.a>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
