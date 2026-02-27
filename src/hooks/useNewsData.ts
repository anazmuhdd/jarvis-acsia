import { useCallback } from "react";
import { useMsal } from "@azure/msal-react";
import { apiService } from "../services/api";

import { deriveUserId, getCachedNews, setCachedNews, clearCachedNews } from "../services/newsCache";
import { getUserProfile, getUserPhoto, getTodoItems, type TodoTask } from "../services/graph";
import { useAppContext, INITIAL_PROFILE } from "../context/AppContext";
import type { UserProfile } from "../services/api";

export function useNewsData() {
  const { accounts } = useMsal();
  const {
    setProfile, setNews, setLoading, setApiError, setTodos, setUserId, setAadObjectId, userId, profile,
    setRecap, setRecapLoading,
  } = useAppContext();

  const fetchNews = useCallback(async (q: string, role: string) => {
    setLoading(true);
    setApiError(null);
    try {
      const articles = await apiService.getNews(q, role);
      return articles;
    } catch {
      setApiError("The connection to the backend was refused. Is the main.py server running?");
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const generateTopicsAndFetch = useCallback(async (targetProfile: UserProfile, uid?: string) => {
    const effectiveUid = uid ?? userId;
    const cached = getCachedNews(effectiveUid);
    if (cached && cached.articles.length > 0) {
      setNews(cached.articles);
      setLoading(false);
      return;
    }
    setLoading(true);
    setApiError(null);
    try {
      const topics = await apiService.generateTopics({ jobTitle: targetProfile.jobTitle, department: targetProfile.department });
      if (topics.length > 0) {
        const articles = await fetchNews(topics.join(","), targetProfile.jobTitle);
        if (articles.length > 0) {
          setNews(articles);
          setCachedNews(effectiveUid, articles, topics);
        }
      } else {
        setLoading(false);
      }
    } catch {
      setApiError("Could not reach the AI backend. Please ensure the backend is running on port 8000.");
      setLoading(false);
    }
  }, [userId, fetchNews]);
  const fetchRecap = useCallback(async (oid: string) => {
    setRecapLoading(true);
    try {
      const data = await apiService.generateRecap(oid);
      setRecap(data.recap_details?.current_recap || "No recap available.");
    } catch (error) {
      console.error("Recap fetch failed:", error);
      setRecap("Failed to load recap.");
    } finally {
      setRecapLoading(false);
    }
  }, [setRecap, setRecapLoading]);

  const loadUserData = useCallback(async () => {
    setLoading(true);
    try {
      const [user, photo, remoteTodos] = await Promise.all([
        getUserProfile(), getUserPhoto(), getTodoItems(),
      ]);
      const newProfile: UserProfile = {
        id: user.id,
        displayName: user.displayName,
        jobTitle: user.jobTitle || "Professional",
        department: user.officeLocation || "Organization",
        photoUrl: photo,
        quote: INITIAL_PROFILE.quote,
      };
      setProfile(newProfile);
      setAadObjectId(user.id);
      const uid = deriveUserId(accounts[0]?.homeAccountId, newProfile.jobTitle, newProfile.department);
      setUserId(uid);
      if (remoteTodos.length > 0) {
        setTodos(remoteTodos.map((t: TodoTask) => ({ 
          id: t.id, 
          listId: t.listId, 
          listName: t.listName,
          wellknownListName: t.wellknownListName,
          text: t.title, 
          done: t.status === "completed" 
        })));
      }
      // Parallel fetch news/topics and recap
      await Promise.all([
        generateTopicsAndFetch(newProfile, uid),
        fetchRecap(user.id)
      ]);
    } catch {
      await generateTopicsAndFetch(INITIAL_PROFILE);
    } finally {
      setLoading(false);
    }
  }, [accounts, generateTopicsAndFetch]);

  const refreshNews = useCallback(async () => {
    clearCachedNews(userId);
    await Promise.all([
      generateTopicsAndFetch(profile, userId),
      profile.id ? fetchRecap(profile.id) : Promise.resolve()
    ]);
  }, [userId, profile, generateTopicsAndFetch, fetchRecap]);

  return { loadUserData, generateTopicsAndFetch, refreshNews, fetchRecap };
}
