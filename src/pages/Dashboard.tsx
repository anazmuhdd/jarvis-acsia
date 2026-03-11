import { useEffect, useState, useCallback, useRef } from "react";
import { Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { loginRequest } from "../services/msalConfig";
import { deriveUserId } from "../services/newsCache";
import { Header } from "../components/Header";
import { ProfileCard } from "../components/ProfileCard";
import { TaskPanel } from "../components/TaskPanel";
import { ArticleDetailPanel } from "../components/ArticleDetailPanel";
import { ArticleList } from "../components/ArticleList";
import { LoginCard } from "../components/LoginCard";
import { useAppContext, INITIAL_PROFILE } from "../context/AppContext";
import { useNewsData } from "../hooks/useNewsData";

const DEFAULT_SIDEBAR_W = 560;
const MIN_SIDEBAR_W = 320;
const MAX_SIDEBAR_VW = 0.6; // 60 vw

export function Dashboard() {
  const { instance, accounts, inProgress } = useMsal();
  const { selectedArticle, setUserId } = useAppContext();
  const { loadUserData, generateTopicsAndFetch } = useNewsData();
  const [authLoading, setAuthLoading] = useState(true);

  /* ── Resizable sidebar state ── */
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_W);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(DEFAULT_SIDEBAR_W);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = sidebarWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [sidebarWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const maxPx = window.innerWidth * MAX_SIDEBAR_VW;
      const newW = Math.min(maxPx, Math.max(MIN_SIDEBAR_W, startW.current + (e.clientX - startX.current)));
      setSidebarWidth(newW);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  useEffect(() => {
    const checkAuth = async () => {
      if (inProgress !== "none") return;
      if (accounts.length > 0) {
        setAuthLoading(false);
        await loadUserData();
      } else {
        const ssoAttempted = sessionStorage.getItem("sso_attempted");
        if (ssoAttempted) {
          setAuthLoading(false);
          const guestId = deriveUserId(undefined, INITIAL_PROFILE.jobTitle, INITIAL_PROFILE.department);
          setUserId(guestId);
          generateTopicsAndFetch(INITIAL_PROFILE, guestId);
          return;
        }
        try {
          sessionStorage.setItem("sso_attempted", "true");
          await instance.ssoSilent(loginRequest);
        } catch {
          const guestId = deriveUserId(undefined, INITIAL_PROFILE.jobTitle, INITIAL_PROFILE.department);
          setUserId(guestId);
          setAuthLoading(false);
          generateTopicsAndFetch(INITIAL_PROFILE, guestId);
        }
      }
    };
    checkAuth();
  }, [accounts, inProgress]);

  if (authLoading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-white">
        <Loader2 size={44} className="text-[#1a73e8] animate-spin" />
        <p className="mt-4 text-gray-400 text-sm">Verifying session…</p>
      </div>
    );
  }

  return (
    <>
      <AuthenticatedTemplate>
        <div className="h-screen bg-white font-sans flex flex-col overflow-hidden">
          <Header />

          {/* ── MAIN TWO-COLUMN LAYOUT ── */}
          <div className="flex-1 flex overflow-hidden">

            {/* ── LEFT COLUMN: Profile (top) + divider + Tasks (bottom) ── */}
            <div className="flex flex-col overflow-hidden border-r border-gray-100 relative"
                 style={{ width: `${sidebarWidth}px`, minWidth: `${MIN_SIDEBAR_W}px` }}>
              {/* Profile section */}
              <div className="shrink-0 px-8 pt-5 pb-3">
                <ProfileCard />
              </div>

              {/* Divider */}
              <div className="h-px bg-gray-100 mx-8 shrink-0" />

              {/* Task panel — fills remaining space */}
              <div className="flex-1 overflow-hidden px-8 py-5 min-h-0">
                <AnimatePresence mode="wait">
                  {selectedArticle ? (
                    <motion.div key="article-detail" className="h-full"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.2 }}>
                      <ArticleDetailPanel />
                    </motion.div>
                  ) : (
                    <motion.div key="task-list" className="h-full"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.2 }}>
                      <TaskPanel />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* ── RESIZE HANDLE ── */}
            <div
              onMouseDown={onMouseDown}
              className="w-1.5 shrink-0 cursor-col-resize group relative z-10
                         hover:bg-[#1a73e8]/10 active:bg-[#1a73e8]/20 transition-colors"
              title="Drag to resize sidebar"
            >
              {/* Grip dots */}
              <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex flex-col items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {[0, 1, 2, 3, 4].map(i => (
                  <div key={i} className="w-[3px] h-[3px] rounded-full bg-[#1a73e8]/40" />
                ))}
              </div>
            </div>

            {/* ── RIGHT COLUMN: Article grid ── */}
            <div className="flex-1 flex flex-col overflow-hidden p-10 min-h-0">
              <ArticleList />
            </div>
          </div>
        </div>
      </AuthenticatedTemplate>

      <UnauthenticatedTemplate>
        <LoginCard />
      </UnauthenticatedTemplate>
    </>
  );
}

