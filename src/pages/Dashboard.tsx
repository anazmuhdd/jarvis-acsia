import { useEffect, useState } from "react";
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

export function Dashboard() {
  const { instance, accounts, inProgress } = useMsal();
  const { selectedArticle, setUserId } = useAppContext();
  const { loadUserData, generateTopicsAndFetch } = useNewsData();
  const [authLoading, setAuthLoading] = useState(true);

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
            <div className="flex flex-col overflow-hidden border-r border-gray-100"
                 style={{ width: "480px", minWidth: "320px" }}>
              {/* Profile section */}
              <div className="shrink-0 px-8 pt-7 pb-5">
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
