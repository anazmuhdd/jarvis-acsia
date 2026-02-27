import { msalInstance, loginRequest } from "./msalConfig";

export async function getAccessToken() {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    try {
      const response = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: accounts[0],
      });
      return response.accessToken;
    } catch (error) {
      console.log("Silent token acquisition failed, acquiring via redirect...", error);
      await msalInstance.acquireTokenRedirect(loginRequest);
      throw new Error("Redirecting for token...");
    }
  }
  throw new Error("No active account found. Please sign in.");
}

export async function getUserProfile() {
  const token = await getAccessToken();
  const response = await fetch("https://graph.microsoft.com/v1.0/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to fetch user profile");
  return response.json();
}

export async function getUserPhoto() {
  try {
    const token = await getAccessToken();
    const response = await fetch("https://graph.microsoft.com/v1.0/me/photo/$value", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) {
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    }
  } catch (error) {
    console.error("Failed to fetch user photo:", error);
  }
  return "https://media.istockphoto.com/id/1175416174/photo/happy-middle-aged-man-laughing-crossing-hands-on-yellow-background.jpg?s=612x612&w=0&k=20&c=uNITBcImFcGbDAtuptkaPK5fER85TJ4IsN11cKKLc-c=";
}

export interface TodoTask {
  id: string;
  listId: string; // Injected for easy CRUD
  listName: string; // Injected for grouping UI
  wellknownListName: string; // Injected for grouping UI
  title: string;
  status: "notStarted" | "inProgress" | "completed" | "deferred" | "waitingOnOthers";
  dueDateTime?: { dateTime: string; timeZone: string };
  createdDateTime: string;
  importance: string;
}

export interface TodoList {
  id: string;
  displayName: string;
  wellknownListName: string;
}

export async function getTodoLists(): Promise<TodoList[]> {
  try {
    const token = await getAccessToken();
    const response = await fetch("https://graph.microsoft.com/v1.0/me/todo/lists", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to fetch todo lists");
    const data = await response.json();
    return data.value || [];
  } catch (error) {
    console.error("Failed to fetch todo lists:", error);
    return [];
  }
}

export async function getTasksForList(listId: string, listName: string, wellknownListName: string): Promise<TodoTask[]> {
  try {
    const token = await getAccessToken();
    const todayStart = new Date();
    todayStart.setUTCHours(0, 0, 0, 0);
    const todayEnd = new Date();
    todayEnd.setUTCHours(23, 59, 59, 999);

    const notCompletedUrl = `https://graph.microsoft.com/v1.0/me/todo/lists/${listId}/tasks?$filter=status ne 'completed'&$orderby=createdDateTime asc`;
    const completedUrl = `https://graph.microsoft.com/v1.0/me/todo/lists/${listId}/tasks?$filter=status eq 'completed'&$orderby=lastModifiedDateTime desc&$top=20`;

    const [notCompletedRes, completedRes] = await Promise.all([
      fetch(notCompletedUrl, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(completedUrl, { headers: { Authorization: `Bearer ${token}` } }),
    ]);

    const notCompletedData = await notCompletedRes.json();
    const completedData = await completedRes.json();

    const allNotCompleted: any[] = notCompletedData.value || [];
    const allCompleted: any[] = completedData.value || [];

    const mapTask = (t: any): TodoTask => ({
      ...t,
      listId,
      listName,
      wellknownListName
    });

    const relevantNotCompleted = allNotCompleted
      .map(mapTask)
      .filter((task) => {
        if (!task.dueDateTime) {
          const created = new Date(task.createdDateTime);
          return created <= todayEnd;
        }
        const due = new Date(task.dueDateTime.dateTime + "Z");
        return due <= todayEnd;
      });

    const completedToday = allCompleted
      .map(mapTask)
      .filter((task) => {
        const modified = new Date(task.createdDateTime);
        return modified >= todayStart && modified <= todayEnd;
      });

    return [...relevantNotCompleted, ...completedToday];
  } catch (error) {
    console.error(`Failed to fetch tasks for list ${listId}:`, error);
    return [];
  }
}

export async function getTodoItems() {
  try {
    const lists = await getTodoLists();
    if (lists.length === 0) return [];
    
    // Filter out flagged emails list
    const validLists = lists.filter((list) => list.wellknownListName !== "flaggedEmails");
    
    const tasksPerList = await Promise.all(validLists.map((list) => getTasksForList(list.id, list.displayName, list.wellknownListName)));
    return tasksPerList.flat();
  } catch (error) {
    console.error("Failed to fetch todo items:", error);
    return [];
  }
}

export async function createTodoTask(listId: string, title: string) {
  const token = await getAccessToken();
  const response = await fetch(`https://graph.microsoft.com/v1.0/me/todo/lists/${listId}/tasks`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error("Failed to create todo task");
  return response.json();
}

export async function updateTodoTask(listId: string, taskId: string, updates: Partial<TodoTask>) {
  const token = await getAccessToken();
  const response = await fetch(`https://graph.microsoft.com/v1.0/me/todo/lists/${listId}/tasks/${taskId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw new Error("Failed to update todo task");
  return response.json();
}

export async function deleteTodoTask(listId: string, taskId: string) {
  const token = await getAccessToken();
  const response = await fetch(`https://graph.microsoft.com/v1.0/me/todo/lists/${listId}/tasks/${taskId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Failed to delete todo task");
}
