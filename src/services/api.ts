const BASE_URL = import.meta.env.VITE_BASE_URL || "https://jarvis-acsia.onrender.com";


export interface Article {
  title: string;
  description: string;
  url: string;
  urlToImage: string | null;
  source: { name: string };
  publishedAt: string;
}

export interface UserProfile {
  displayName: string;
  jobTitle: string;
  department: string;
  photoUrl?: string;
  quote?: string;
}

export interface NewsResponse {
  articles: Article[];
}

export interface TopicsResponse {
  queries: string[];
}

export const apiService = {
  /**
   * Fetches news articles based on a query and user role.
   */
  async getNews(q: string, role: string): Promise<Article[]> {
    try {
      const url = new URL(`${BASE_URL}/api/news`);
      url.searchParams.append("q", q);
      url.searchParams.append("role", role);

      const response = await fetch(url.toString());
      if (!response.ok) {
        throw new Error(`Error fetching news: ${response.statusText}`);
      }
      const data: NewsResponse = await response.json();
      return data.articles || [];
    } catch (error) {
      console.error("API Error (getNews):", error);
      throw error;
    }
  },

  /**
   * Generates high-quality search queries based on the user's professional profile.
   */
  async generateTopics(profile: Pick<UserProfile, 'jobTitle' | 'department'>): Promise<string[]> {
    try {
      const response = await fetch(`${BASE_URL}/api/generate-topics`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role: profile.jobTitle,
          department: profile.department,
        }),
      });

      if (!response.ok) {
        throw new Error(`Error generating topics: ${response.statusText}`);
      }

      const data: TopicsResponse = await response.json();
      return data.queries || [];
    } catch (error) {
      console.error("API Error (generateTopics):", error);
      throw error;
    }
  },
};
