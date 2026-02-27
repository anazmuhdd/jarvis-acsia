import { createContext, useContext, useState, type ReactNode } from "react";
import type { Article, UserProfile } from "../services/api";

export interface TodoItem {
  id: string;
  listId: string;
  text: string;
  done: boolean;
}

export const INITIAL_PROFILE: UserProfile = {
  id: "",
  displayName: "Mohammed Anas A R",
  jobTitle: "AI Engineer",
  department: "Innovic",
  photoUrl: "https://www.istockphoto.com/photos/laughing-model-in-orange-studio",
  quote: "The best way to predict the future is to build it — one model at a time.",
};

interface AppContextValue {
  profile: UserProfile;
  setProfile: (p: UserProfile) => void;
  news: Article[];
  setNews: (a: Article[]) => void;
  loading: boolean;
  setLoading: (l: boolean) => void;
  apiError: string | null;
  setApiError: (e: string | null) => void;
  todos: TodoItem[];
  setTodos: React.Dispatch<React.SetStateAction<TodoItem[]>>;
  selectedArticle: Article | null;
  setSelectedArticle: (a: Article | null) => void;
  userId: string;
  setUserId: (id: string) => void;
  aadObjectId: string | null;
  setAadObjectId: (id: string | null) => void;
  recap: string | null;
  setRecap: (r: string | null) => void;
  recapLoading: boolean;
  setRecapLoading: (l: boolean) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile>(INITIAL_PROFILE);
  const [news, setNews] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [userId, setUserId] = useState("guest");
  const [aadObjectId, setAadObjectId] = useState<string | null>(null);
  const [recap, setRecap] = useState<string | null>(null);
  const [recapLoading, setRecapLoading] = useState(false);

  return (
    <AppContext.Provider value={{
      profile, setProfile,
      news, setNews,
      loading, setLoading,
      apiError, setApiError,
      todos, setTodos,
      selectedArticle, setSelectedArticle,
      userId, setUserId,
      aadObjectId, setAadObjectId,
      recap, setRecap,
      recapLoading, setRecapLoading,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}
