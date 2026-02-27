import { useState } from "react";
import { useAppContext } from "../context/AppContext";

export function useTodos() {
  const { todos, setTodos } = useAppContext();
  const [newTodoTitle, setNewTodoTitle] = useState("");

  const toggleTodo = async (id: string) => {
    const todo = todos.find(t => t.id === id);
    if (!todo) return;
    const newDone = !todo.done;
    setTodos(prev => prev.map(t => t.id === id ? { ...t, done: newDone } : t));
    try {
      if (todo.listId !== "default") {
        const { updateTodoTask } = await import("../services/graph");
        await updateTodoTask(todo.listId, todo.id, { status: newDone ? "completed" : "notStarted" });
      }
    } catch {
      setTodos(prev => prev.map(t => t.id === id ? { ...t, done: !newDone } : t));
    }
  };

  const addTodo = async (text: string) => {
    if (!text.trim()) return;
    try {
      const { getTodoLists, createTodoTask } = await import("../services/graph");
      const lists = await getTodoLists();
      const defaultList = lists.find((l: any) => l.displayName === "Tasks") || lists[0];
      if (defaultList) {
        const newTask = await createTodoTask(defaultList.id, text);
        setTodos(prev => [{ id: newTask.id, listId: defaultList.id, text: newTask.title, done: newTask.status === "completed" }, ...prev]);
      }
    } catch (e) { console.error("Failed to add task:", e); }
  };

  const deleteTodo = async (id: string) => {
    const todo = todos.find(t => t.id === id);
    if (!todo) return;
    setTodos(prev => prev.filter(t => t.id !== id));
    try {
      if (todo.listId !== "default") {
        const { deleteTodoTask } = await import("../services/graph");
        await deleteTodoTask(todo.listId, todo.id);
      }
    } catch {
      setTodos(prev => [...prev, todo]);
    }
  };

  const handleAddTodo = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && newTodoTitle.trim()) {
      addTodo(newTodoTitle.trim());
      setNewTodoTitle("");
    }
  };

  return { todos, newTodoTitle, setNewTodoTitle, toggleTodo, addTodo, deleteTodo, handleAddTodo };
}
