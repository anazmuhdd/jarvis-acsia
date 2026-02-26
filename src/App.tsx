import { useEffect, useState } from "react";
import {
  Search, Loader2, Quote, CheckSquare, Square,
  Newspaper, ChevronRight, Briefcase, LogIn, RefreshCw
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { format } from "date-fns";
import { apiService, type Article, type UserProfile } from "./services/api";
import { deriveUserId, getCachedNews, setCachedNews, clearCachedNews } from "./services/newsCache";
import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import { loginRequest } from "./services/msalConfig";
import { getUserProfile, getUserPhoto, getTodoItems, type TodoTask } from "./services/graph";

interface TodoItem {
  id: string; // Changed to string to use Graph's taskId
  listId: string;
  text: string;
  done: boolean;
}

const INITIAL_PROFILE: UserProfile = {
  displayName: "Mohammed Anas A R",
  jobTitle: "AI Engineer",
  department: "Innovic",
  photoUrl: "https://api.dicebear.com/7.x/avataaars/svg?seed=AnasAR",
  quote:
    "The best way to predict the future is to build it — one model at a time.",
};

const INITIAL_TODOS: TodoItem[] = [];

function App() {
  const { instance, accounts, inProgress } = useMsal();
  const [profile, setProfile] = useState<UserProfile>(INITIAL_PROFILE);
  const [news, setNews] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const suggestionTimeoutRef = { current: null as ReturnType<typeof setTimeout> | null };
  const [todos, setTodos] = useState<TodoItem[]>(INITIAL_TODOS);
  const [userId, setUserId] = useState<string>("guest");

  useEffect(() => {
    const checkAuth = async () => {
      // Only proceed if MSAL is idle
      if (inProgress !== "none") return;

      if (accounts.length > 0) {
        setAuthLoading(false);
        await loadUserData();
      } else {
        // Prevent infinite silent SSO loops if it keeps failing
        const ssoAttempted = sessionStorage.getItem("sso_attempted");
        if (ssoAttempted) {
          setAuthLoading(false);
          const guestId = deriveUserId(undefined, INITIAL_PROFILE.jobTitle, INITIAL_PROFILE.department);
          setUserId(guestId);
          generateTopicsAndFetchWithProfile(INITIAL_PROFILE, guestId);
          return;
        }

        try {
          sessionStorage.setItem("sso_attempted", "true");
          // Attempt silent SSO, but catch it properly
          await instance.ssoSilent(loginRequest);
        } catch (error) {
          console.log("Silent SSO fallback (expected if not pre-logged in):", error);
          const guestId = deriveUserId(undefined, INITIAL_PROFILE.jobTitle, INITIAL_PROFILE.department);
          setUserId(guestId);
          setAuthLoading(false);
          generateTopicsAndFetchWithProfile(INITIAL_PROFILE, guestId);
        }
      }
    };
    checkAuth();
  }, [accounts, inProgress]);

  const loadUserData = async () => {
    setLoading(true);
    try {
      const [user, photo, remoteTodos] = await Promise.all([
        getUserProfile(),
        getUserPhoto(),
        getTodoItems()
      ]);

      const newProfile: UserProfile = {
        displayName: user.displayName,
        jobTitle: user.jobTitle || "Professional",
        department: user.officeLocation || "Organization",
        photoUrl: photo,
        quote: INITIAL_PROFILE.quote
      };

      setProfile(newProfile);

      // Derive a stable user ID from the MSAL account + profile
      const uid = deriveUserId(
        accounts[0]?.homeAccountId,
        newProfile.jobTitle,
        newProfile.department
      );
      setUserId(uid);

      if (remoteTodos.length > 0) {
        setTodos(remoteTodos.map((t: TodoTask) => ({
          id: t.id,
          listId: t.listId,
          text: t.title,
          done: t.status === "completed",
        })));
      }

      await generateTopicsAndFetchWithProfile(newProfile, uid);
    } catch (error) {
      console.error("Failed to load user data from Graph:", error);
      await generateTopicsAndFetchWithProfile(INITIAL_PROFILE);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    // Use loginRedirect instead of loginPopup to avoid the popup getting stuck
    instance.loginRedirect(loginRequest).catch(e => {
      console.error(e);
    });
  };

  const fetchNews = async (q: string, role: string): Promise<Article[]> => {
    setLoading(true);
    setApiError(null);
    try {
      const articles = await apiService.getNews(q, role);
      return articles;
    } catch (error) {
      console.error("Failed to fetch news:", error);
      setApiError("The connection to the backend was refused. Is the main.py server running?");
      return [];
    } finally {
      setLoading(false);
    }
  };

  const generateTopicsAndFetchWithProfile = async (
    targetProfile: UserProfile,
    uid?: string
  ) => {
    const effectiveUid = uid ?? userId;

    // --- Cache-first check ---
    const cached = getCachedNews(effectiveUid);
    if (cached && cached.articles.length > 0) {
      setNews(cached.articles);
      setLoading(false);
      return;
    }

    // --- Live fetch ---
    setLoading(true);
    setApiError(null);
    try {
      const topics = await apiService.generateTopics({
        jobTitle: targetProfile.jobTitle,
        department: targetProfile.department,
      });
      if (topics.length > 0) {
        const articles = await fetchNews(topics.join(","), targetProfile.jobTitle);
        if (articles.length > 0) {
          setNews(articles);
          setCachedNews(effectiveUid, articles, topics);
        }
      } else {
        setLoading(false);
      }
    } catch (error) {
      console.error("Failed to generate topics:", error);
      setApiError("Could not reach the AI backend. Please ensure the backend is running on port 8000.");
      setLoading(false);
    }
  };

  const refreshNews = async () => {
    clearCachedNews(userId);
    await generateTopicsAndFetchWithProfile(profile, userId);
  };

  const fetchSuggestions = async (query: string) => {
    if (!query.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    try {
      // Routed through Vite proxy → ac.duckduckgo.com/ac/ (proxy injects CORS headers)
      const res = await fetch(
        `/api/suggest?q=${encodeURIComponent(query)}&type=list`,
        { signal: AbortSignal.timeout(3000) }
      );
      if (res.ok) {
        const data = await res.json();
        // data[1] is the array of suggestion strings
        setSuggestions((data[1] as string[]).slice(0, 8));
        setShowSuggestions(true);
      }
    } catch {
      setSuggestions([]);
    }
  };

  const handleSearchInput = (value: string) => {
    setSearchQuery(value);
    setActiveSuggestion(-1);
    if (suggestionTimeoutRef.current) clearTimeout(suggestionTimeoutRef.current);
    suggestionTimeoutRef.current = setTimeout(() => fetchSuggestions(value), 200);
  };

  const openGoogleSearch = (query: string) => {
    if (!query.trim()) return;
    window.open(`https://www.google.com/search?q=${encodeURIComponent(query.trim())}`, "_blank", "noopener,noreferrer");
    setShowSuggestions(false);
  };

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestion(prev => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestion(prev => Math.max(prev - 1, -1));
    } else if (e.key === "Enter") {
      const query = activeSuggestion >= 0 ? suggestions[activeSuggestion] : searchQuery;
      openGoogleSearch(query);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  const toggleTodo = async (id: string) => {
    const todo = todos.find(t => t.id === id);
    if (!todo) return;

    const newDone = !todo.done;
    
    // Optimistic update
    setTodos((prev: TodoItem[]) =>
      prev.map((t: TodoItem) => (t.id === id ? { ...t, done: newDone } : t))
    );

    try {
      // If it's a real Graph task (listId !== 'default')
      if (todo.listId !== 'default') {
        const { updateTodoTask } = await import("./services/graph");
        await updateTodoTask(todo.listId, todo.id, {
          status: newDone ? "completed" : "notStarted"
        });
      }
    } catch (error) {
      console.error("Failed to update task status in Graph:", error);
      // Revert on error
      setTodos((prev: TodoItem[]) =>
        prev.map((t: TodoItem) => (t.id === id ? { ...t, done: !newDone } : t))
      );
    }
  };

  const addTodo = async (text: string) => {
    if (!text.trim()) return;

    try {
      const { getTodoLists, createTodoTask } = await import("./services/graph");
      const lists = await getTodoLists();
      const defaultList = lists.find((l: any) => l.displayName === "Tasks") || lists[0];
      
      if (defaultList) {
        const newTask = await createTodoTask(defaultList.id, text);
        setTodos((prev: TodoItem[]) => [
          {
            id: newTask.id,
            listId: defaultList.id,
            text: newTask.title,
            done: newTask.status === "completed"
          },
          ...prev
        ]);
      }
    } catch (error) {
      console.error("Failed to add task to Graph:", error);
    }
  };

  const deleteTodo = async (id: string) => {
    const todo = todos.find(t => t.id === id);
    if (!todo) return;

    // Optimistic delete
    setTodos((prev: TodoItem[]) => prev.filter(t => t.id !== id));

    try {
      if (todo.listId !== 'default') {
        const { deleteTodoTask } = await import("./services/graph");
        await deleteTodoTask(todo.listId, todo.id);
      }
    } catch (error) {
      console.error("Failed to delete task from Graph:", error);
      // Revert on error
      setTodos((prev: TodoItem[]) => [...prev, todo]);
    }
  };

  const [newTodoTitle, setNewTodoTitle] = useState("");

  const handleAddTodo = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && newTodoTitle.trim()) {
      addTodo(newTodoTitle.trim());
      setNewTodoTitle("");
    }
  };

  const cleanDescription = (text: string): string => {
    if (!text) return "";
    return text
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'")
      .replace(/&[a-z]+;/gi, " ") // catch-all for other named entities
      .replace(/\s+/g, " ")
      .trim();
  };

  const getCardStyle = (idx: number, hasImage: boolean): React.CSSProperties => {
    if (idx === 0) {
      return {
        gridColumn: "1 / -1",
        display: "grid",
        gridTemplateColumns: hasImage ? "1.3fr 1fr" : "1fr",
        minHeight: "340px",
      };
    }
    if (idx === 1 || idx === 2) {
      return { minHeight: "320px", display: "flex", flexDirection: "column" };
    }
    if (idx % 5 === 3) {
      return { gridColumn: "span 2", minHeight: "260px", display: "flex", flexDirection: "column" };
    }
    return { minHeight: "280px", display: "flex", flexDirection: "column" };
  };

  if (authLoading) {
    return (
      <div style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-main)",
        fontFamily: "var(--font-main)"
      }}>
        <Loader2 className="animate-spin" size={48} color="var(--accent)" />
        <p style={{ marginTop: "1rem", color: "var(--text-secondary)" }}>Verifying session…</p>
      </div>
    );
  }

  return (
    <>
      <AuthenticatedTemplate>
        <main style={{ minHeight: "100vh", background: "var(--bg-main)" }}>
          <div
            style={{
              position: "relative",
              width: "100%",
              height: "15vh",
              minHeight: "120px",
              overflow: "hidden",
            }}
          >
            <img
              src="/background.jpeg"
              alt=""
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
            <div
              style={{
                position: "absolute",
                inset: 0,
                backdropFilter: "blur(6px)",
                WebkitBackdropFilter: "blur(6px)",
                background: "rgba(255,255,255,0.25)",
              }}
            />
            <div
              style={{
                position: "relative",
                zIndex: 2,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                padding: "0 2rem",
              }}
            >
              <div
                style={{
                  position: "relative",
                  width: "100%",
                  maxWidth: "680px",
                }}
                onBlur={(e) => {
                  // Hide suggestions only if focus left the whole container
                  if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                    setShowSuggestions(false);
                  }
                }}
              >
                {/* Search Input Row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    background: "rgba(255,255,255,0.92)",
                    borderRadius: showSuggestions && suggestions.length > 0 ? "18px 18px 0 0" : "28px",
                    padding: "0 20px",
                    boxShadow: "0 4px 24px rgba(0,0,0,0.12)",
                    border: "1px solid rgba(255,255,255,0.6)",
                    transition: "border-radius 0.15s ease",
                  }}
                >
                  <Search size={20} color="#5f6368" style={{ flexShrink: 0 }} />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => handleSearchInput(e.target.value)}
                    onKeyDown={handleSearch}
                    onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                    placeholder="Search Google…"
                    style={{
                      flex: 1,
                      border: "none",
                      outline: "none",
                      background: "transparent",
                      padding: "14px 14px",
                      fontSize: "0.95rem",
                      fontFamily: "var(--font-main)",
                      color: "#202124",
                    }}
                  />
                  {searchQuery && (
                    <button
                      onClick={() => { setSearchQuery(""); setSuggestions([]); setShowSuggestions(false); }}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        padding: "4px",
                        color: "#5f6368",
                        fontSize: "1rem",
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                      tabIndex={-1}
                      aria-label="Clear search"
                    >✕</button>
                  )}
                </div>

                {/* Suggestions Dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                  <div
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      background: "rgba(255,255,255,0.97)",
                      borderRadius: "0 0 18px 18px",
                      boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
                      border: "1px solid rgba(255,255,255,0.6)",
                      borderTop: "1px solid #e8eaed",
                      zIndex: 100,
                      overflow: "hidden",
                    }}
                  >
                    {suggestions.map((s, i) => (
                      <div
                        key={s}
                        tabIndex={0}
                        onMouseDown={(e) => { e.preventDefault(); openGoogleSearch(s); }}
                        onMouseEnter={() => setActiveSuggestion(i)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "12px",
                          padding: "10px 20px",
                          cursor: "pointer",
                          background: activeSuggestion === i ? "#f1f3f4" : "transparent",
                          fontSize: "0.9rem",
                          color: "#202124",
                          fontFamily: "var(--font-main)",
                          transition: "background 0.1s",
                        }}
                      >
                        <Search size={14} color="#9aa0a6" style={{ flexShrink: 0 }} />
                        <span>{s}</span>
                        <span
                          style={{
                            marginLeft: "auto",
                            fontSize: "0.7rem",
                            color: "#9aa0a6",
                            whiteSpace: "nowrap",
                          }}
                        >
                          ↗ Google
                        </span>
                      </div>
                    ))}
                    <div
                      style={{
                        padding: "8px 20px",
                        fontSize: "0.72rem",
                        color: "#9aa0a6",
                        borderTop: "1px solid #f1f3f4",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <span>Powered by</span>
                      <strong style={{ color: "#4285f4" }}>Google</strong>
                      <span>Search</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div
            style={{
              maxWidth: "1440px",
              margin: "0 auto",
              padding: "2rem 2.5rem",
              display: "grid",
              gridTemplateColumns: "1fr 340px",
              gap: "2.5rem",
              alignItems: "start",
            }}
          >
            <section>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1.5rem",
                }}
              >
                <h1
                    style={{
                      fontSize: "1.6rem",
                      fontWeight: 800,
                      letterSpacing: "-0.03em",
                    }}
                  >
                    Top Stories
                  </h1>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-muted)",
                      fontWeight: 500,
                    }}
                  >
                    {format(new Date(), "EEEE, MMMM d, yyyy")}
                  </span>
                  <button
                    onClick={refreshNews}
                    disabled={loading}
                    title="Force refresh — bypasses cache"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      background: "none",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                      padding: "4px 10px",
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      cursor: loading ? "not-allowed" : "pointer",
                      opacity: loading ? 0.5 : 1,
                      transition: "opacity 0.2s",
                      fontFamily: "var(--font-main)",
                    }}
                  >
                    <RefreshCw size={12} />
                    Refresh
                  </button>
                </div>
              </div>

              {loading && news.length === 0 ? (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "400px",
                    gap: "1rem",
                  }}
                >
                  <Loader2
                    className="animate-spin"
                    size={36}
                    color="var(--accent)"
                    style={{ animation: "spin 1s linear infinite" }}
                  />
                  <p style={{ color: "var(--text-muted)", fontSize: "1rem" }}>
                    Fetching latest stories…
                  </p>
                  <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
                </div>
              ) : apiError ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "3rem 2rem",
                    background: "#fff5f5",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid #feb2b2",
                    color: "#c53030",
                  }}
                >
                  <h3 style={{ marginBottom: "0.5rem" }}>Backend Connection Error</h3>
                  <p style={{ fontSize: "0.9rem" }}>{apiError}</p>
                </div>
              ) : news.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "5rem 2rem",
                    background: "var(--bg-white)",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <Newspaper
                    size={48}
                    color="var(--border)"
                    style={{ marginBottom: "1rem" }}
                  />
                  <h3
                    style={{
                      color: "var(--text-secondary)",
                      marginBottom: "0.5rem",
                    }}
                  >
                    No stories yet
                  </h3>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                    Search for a topic to start reading.
                  </p>
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "1.25rem",
                  }}
                >
                  <AnimatePresence mode="popLayout">
                    {news.map((article: Article, idx: number) => {
                      const isHero = idx === 0;
                      const hasImage = !!article.urlToImage;
                      const cardStyle = getCardStyle(idx, hasImage);

                      return (
                        <motion.a
                          key={article.url + idx}
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          initial={{ opacity: 0, y: 16 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.97 }}
                          transition={{
                            duration: 0.35,
                            delay: Math.min(idx, 8) * 0.06,
                          }}
                          style={{
                            ...cardStyle,
                            background: "var(--bg-white)",
                            borderRadius: "var(--radius-lg)",
                            overflow: "hidden",
                            border: "1px solid var(--border-light)",
                            boxShadow: "var(--shadow-sm)",
                            transition:
                              "box-shadow 0.25s ease, transform 0.25s ease",
                            cursor: "pointer",
                            textDecoration: "none",
                            color: "inherit",
                          }}
                          whileHover={{
                            y: -3,
                            boxShadow: "0 6px 20px rgba(0,0,0,0.1)",
                          }}
                        >
                          {isHero ? (
                            <>
                              {hasImage && (
                                <div
                                  style={{
                                    overflow: "hidden",
                                    borderRadius:
                                      "var(--radius-lg) 0 0 var(--radius-lg)",
                                  }}
                                >
                                  <img
                                    src={article.urlToImage!}
                                    alt={article.title}
                                    style={{
                                      width: "100%",
                                      height: "100%",
                                      objectFit: "cover",
                                    }}
                                  />
                                </div>
                              )}
                              <div
                                style={{
                                  padding: "2rem",
                                  display: "flex",
                                  flexDirection: "column",
                                  justifyContent: "center",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: "0.7rem",
                                    fontWeight: 700,
                                    textTransform: "uppercase",
                                    color: "var(--accent)",
                                    letterSpacing: "0.06em",
                                    marginBottom: "0.6rem",
                                  }}
                                >
                                  {article.source.name}
                                </span>
                                <h2
                                  style={{
                                    fontSize: hasImage ? "1.45rem" : "1.8rem",
                                    lineHeight: 1.35,
                                    marginBottom: "1rem",
                                    fontWeight: 800,
                                    letterSpacing: "-0.02em",
                                  }}
                                >
                                  {article.title}
                                </h2>
                                <p
                                  style={{
                                    fontSize: "0.95rem",
                                    color: "var(--text-secondary)",
                                    lineHeight: 1.6,
                                    display: "-webkit-box",
                                    WebkitLineClamp: hasImage ? 3 : 5,
                                    WebkitBoxOrient: "vertical",
                                    overflow: "hidden",
                                    marginBottom: "1.2rem",
                                  }}
                                >
                                  {cleanDescription(article.description)}
                                </p>
                              </div>
                            </>
                          ) : (
                            <>
                              {hasImage && (
                                <div
                                  style={{
                                    height: "55%",
                                    overflow: "hidden",
                                    position: "relative",
                                  }}
                                >
                                  <img
                                    src={article.urlToImage!}
                                    alt={article.title}
                                    style={{
                                      width: "100%",
                                      height: "100%",
                                      objectFit: "cover",
                                      transition: "transform 0.4s ease",
                                    }}
                                  />
                                  <span
                                    style={{
                                      position: "absolute",
                                      bottom: "8px",
                                      left: "8px",
                                      padding: "3px 8px",
                                      borderRadius: "6px",
                                      background: "rgba(0,0,0,0.6)",
                                      color: "#fff",
                                      fontSize: "0.65rem",
                                      fontWeight: 600,
                                      backdropFilter: "blur(4px)",
                                    }}
                                  >
                                    {article.source.name}
                                  </span>
                                </div>
                              )}
                              <div
                                style={{
                                  padding: hasImage ? "1rem 1.2rem" : "1.5rem",
                                  display: "flex",
                                  flexDirection: "column",
                                  flex: 1,
                                }}
                              >
                                {!hasImage && (
                                  <span
                                    style={{
                                      fontSize: "0.65rem",
                                      fontWeight: 700,
                                      textTransform: "uppercase",
                                      color: "var(--accent)",
                                      letterSpacing: "0.06em",
                                      marginBottom: "0.5rem",
                                    }}
                                  >
                                    {article.source.name}
                                  </span>
                                )}
                                <h3
                                  style={{
                                    fontSize: hasImage ? "0.95rem" : "1.1rem",
                                    lineHeight: 1.4,
                                    fontWeight: 700,
                                    marginBottom: "0.5rem",
                                    display: "-webkit-box",
                                    WebkitLineClamp: hasImage ? 3 : 5,
                                    WebkitBoxOrient: "vertical",
                                    overflow: "hidden",
                                  }}
                                >
                                  {article.title}
                                </h3>
                                <p
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                    lineHeight: 1.5,
                                    display: "-webkit-box",
                                    WebkitLineClamp: hasImage ? 2 : 4,
                                    WebkitBoxOrient: "vertical",
                                    overflow: "hidden",
                                    flex: 1,
                                  }}
                                >
                                  {cleanDescription(article.description)}
                                </p>
                                 <div
                                   style={{
                                     display: "flex",
                                     justifyContent: "flex-end",
                                     marginTop: "0.8rem",
                                   }}
                                 >
                                   <ChevronRight size={14} color="var(--accent)" />
                                 </div>
                              </div>
                            </>
                          )}
                        </motion.a>
                      );
                    })}
                  </AnimatePresence>
                </div>
              )}
            </section>

            <aside style={{ display: "flex", flexDirection: "column", gap: "1.25rem", position: "sticky", top: "1.5rem" }}>
              <motion.div
                initial={{ x: 20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ duration: 0.5 }}
                style={{
                  background: "var(--bg-white)",
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--border-light)",
                  boxShadow: "var(--shadow-sm)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "6px",
                    background: "linear-gradient(90deg, #1a73e8, #4285f4, #34a853, #fbbc04, #ea4335)",
                  }}
                />
                <div style={{ padding: "1.5rem" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "1rem",
                      marginBottom: "1.2rem",
                    }}
                  >
                    <div
                      style={{
                        width: "56px",
                        height: "56px",
                        borderRadius: "50%",
                        overflow: "hidden",
                        border: "3px solid var(--accent-light)",
                        flexShrink: 0,
                      }}
                    >
                      <img
                        src={profile.photoUrl}
                        alt={profile.displayName}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    </div>
                    <div>
                      <h3
                        style={{
                          fontSize: "1.05rem",
                          fontWeight: 700,
                          lineHeight: 1.2,
                        }}
                      >
                        {profile.displayName}
                      </h3>
                      <p
                        style={{
                          fontSize: "0.78rem",
                          color: "var(--text-secondary)",
                          marginTop: "2px",
                        }}
                      >
                        {profile.jobTitle}
                      </p>
                    </div>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.6rem",
                      marginBottom: "1.2rem",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        fontSize: "0.8rem",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <Briefcase size={14} color="var(--accent)" />
                      <span>{profile.department}</span>
                    </div>
                  </div>

                  <div
                    style={{
                      background: "#f8f9fa",
                      borderRadius: "var(--radius)",
                      padding: "1rem",
                      borderLeft: "3px solid var(--accent)",
                    }}
                  >
                    <Quote
                      size={16}
                      color="var(--accent)"
                      style={{ marginBottom: "6px" }}
                    />
                    <p
                      style={{
                        fontSize: "0.82rem",
                        fontStyle: "italic",
                        lineHeight: 1.55,
                        color: "var(--text-secondary)",
                      }}
                    >
                      &ldquo;{profile.quote}&rdquo;
                    </p>
                  </div>
                </div>
              </motion.div>

              <motion.div
                initial={{ x: 20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.15 }}
                style={{
                  background: "var(--bg-white)",
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--border-light)",
                  boxShadow: "var(--shadow-sm)",
                  padding: "1.25rem 1.5rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "1rem",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "0.95rem",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckSquare size={16} color="var(--accent)" />
                    To Do
                  </h3>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      color: "var(--text-muted)",
                      fontWeight: 500,
                    }}
                  >
                    {todos.length > 0 ? `${todos.filter((t) => t.done).length}/${todos.length} done` : "No tasks"}
                  </span>
                </div>

                {todos.length > 0 && (
                  <div
                    style={{
                      height: "4px",
                      borderRadius: "4px",
                      background: "#eee",
                      marginBottom: "1rem",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        borderRadius: "4px",
                        width: `${(todos.filter((t) => t.done).length / todos.length) * 100}%`,
                        background: "linear-gradient(90deg, var(--accent), #34a853)",
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>
                )}

                <div style={{ marginBottom: "1rem" }}>
                  <input
                    type="text"
                    placeholder="Add new task..."
                    value={newTodoTitle}
                    onChange={(e) => setNewTodoTitle(e.target.value)}
                    onKeyDown={handleAddTodo}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "#f8f9fa",
                      border: "1px solid var(--border-light)",
                      borderRadius: "8px",
                      fontSize: "0.8rem",
                      outline: "none",
                    }}
                  />
                </div>

                <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "2px" }}>
                  {todos.map((todo: TodoItem) => (
                    <li
                      key={todo.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "8px 6px",
                        borderRadius: "8px",
                        fontSize: "0.82rem",
                        transition: "background 0.15s ease",
                        userSelect: "none",
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.background = "#f1f3f4")}
                      onMouseOut={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <div
                        onClick={() => toggleTodo(todo.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          flex: 1,
                          cursor: "pointer",
                          color: todo.done ? "var(--text-muted)" : "var(--text-primary)",
                          textDecoration: todo.done ? "line-through" : "none",
                        }}
                      >
                        {todo.done ? (
                          <CheckSquare size={16} color="var(--accent-green)" />
                        ) : (
                          <Square size={16} color="var(--border)" />
                        )}
                        {todo.text}
                      </div>
                      <button
                        onClick={() => deleteTodo(todo.id)}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#ff4d4d",
                          cursor: "pointer",
                          padding: "4px",
                          fontSize: "1.1rem",
                          lineHeight: 1,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        title="Delete task"
                      >
                        &times;
                      </button>
                    </li>
                  ))}
                  {todos.length === 0 && (
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "center", padding: "10px" }}>
                      No tasks found in Microsoft To-Do.
                    </p>
                  )}
                </ul>
              </motion.div>
            </aside>
          </div>
        </main>
      </AuthenticatedTemplate>

      <UnauthenticatedTemplate>
        <div style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-main)",
          fontFamily: "var(--font-main)"
        }}>
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              padding: "3rem",
              background: "var(--bg-white)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "0 10px 40px rgba(0,0,0,0.12)",
              textAlign: "center",
              maxWidth: "400px"
            }}
          >
            <div style={{
              width: "64px",
              height: "64px",
              background: "var(--accent-light)",
              borderRadius: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1.5rem"
            }}>
              <LogIn size={32} color="var(--accent)" />
            </div>
            <h2 style={{ fontSize: "1.5rem", fontWeight: 800, marginBottom: "1rem" }}>Welcome Back</h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>
              Sign in with your Microsoft account to access your professional intelligence dashboard.
            </p>
            <button
              onClick={handleLogin}
              style={{
                width: "100%",
                padding: "12px 24px",
                background: "var(--accent)",
                color: "white",
                border: "none",
                borderRadius: "12px",
                fontSize: "1rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "10px",
                transition: "transform 0.2s"
              }}
              onMouseOver={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
              onMouseOut={(e) => (e.currentTarget.style.transform = "translateY(0)")}
            >
              Sign in with Microsoft
            </button>
          </motion.div>
        </div>
      </UnauthenticatedTemplate>
    </>
  );
}

export default App;
