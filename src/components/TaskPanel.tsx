import { useState } from "react";
import { CheckSquare, Square, X, ChevronDown, ChevronRight, Folder } from "lucide-react";
import { useAppContext } from "../context/AppContext";
import { useTodos } from "../hooks/useTodos";

export function TaskPanel() {
  const { todos, todoLists } = useAppContext();
  const { newTodoTitle, setNewTodoTitle, toggleTodo, deleteTodo, handleAddTodo } = useTodos();
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const doneCount = todos.filter(t => t.done).length;
  const progressPct = todos.length > 0 ? (doneCount / todos.length) * 100 : 0;

  // Separate tasks into default and grouped
  const defaultTasks = todos.filter(t => t.wellknownListName === "defaultList");
  
  // Use explicitly fetched lists instead of deriving from tasks to show empty lists
  const otherLists = todoLists.filter(list => list.wellknownListName !== "defaultList");

  const toggleGroup = (listId: string) => {
    setExpandedGroups(prev => ({ ...prev, [listId]: !prev[listId] }));
  };

  const renderTask = (todo: typeof todos[0]) => (
    <li key={todo.id}
      className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-gray-50 transition-colors group">
      <div onClick={() => toggleTodo(todo.id)} className="flex items-center gap-2.5 flex-1 cursor-pointer min-w-0">
        {todo.done
          ? <CheckSquare size={14} className="text-[#34a853] shrink-0" />
          : <Square size={14} className="text-gray-300 shrink-0" />}
        <span className={`text-xs truncate ${todo.done ? "line-through text-gray-400" : "text-gray-700"}`}>
          {todo.text}
        </span>
      </div>
      <button onClick={() => deleteTodo(todo.id)}
        className="text-gray-300 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <X size={12} />
      </button>
    </li>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Title */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <CheckSquare size={15} className="text-[#1a73e8]" /> My Tasks
        </h3>
        <span className="text-xs text-gray-400">
          {todos.length > 0 ? `${doneCount}/${todos.length}` : "empty"}
        </span>
      </div>

      {/* Progress bar */}
      {todos.length > 0 && (
        <div className="h-0.5 rounded-full bg-gray-100 mb-3 shrink-0 overflow-hidden">
          <div className="h-full rounded-full bg-[#1a73e8] transition-all duration-500"
            style={{ width: `${progressPct}%` }} />
        </div>
      )}

      {/* Add task */}
      <input
        type="text"
        placeholder="Add task… (Enter)"
        value={newTodoTitle}
        onChange={e => setNewTodoTitle(e.target.value)}
        onKeyDown={handleAddTodo}
        className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-700
                   outline-none focus:ring-1 focus:ring-[#1a73e8]/40 focus:border-[#1a73e8] mb-2 transition-all shrink-0" />

      {/* Task list — scrollable */}
      <div className="flex flex-col gap-0.5 overflow-y-auto flex-1 min-h-0 pr-1 pb-4">
        {/* Default Tasks */}
        <ul className="flex flex-col gap-0.5">
          {defaultTasks.map(renderTask)}
        </ul>

        {/* Grouped Tasks */}
        {otherLists.map(list => {
          const isExpanded = expandedGroups[list.id];
          const tasks = todos.filter(t => t.listId === list.id);
          return (
            <div key={list.id} className="mt-2">
              <button 
                onClick={() => toggleGroup(list.id)}
                className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-gray-50 rounded-lg transition-colors group cursor-pointer"
              >
                {isExpanded ? (
                  <ChevronDown size={14} className="text-gray-400" />
                ) : (
                  <ChevronRight size={14} className="text-gray-400" />
                )}
                <Folder size={13} className="text-[#1a73e8] opacity-70" />
                <span className="text-xs font-medium text-gray-600 truncate">{list.displayName}</span>
                <span className="text-[10px] text-gray-400 ml-auto bg-gray-100 px-1.5 py-0.5 rounded-full">
                  {tasks.length}
                </span>
              </button>
              
              {isExpanded && tasks.length > 0 && (
                <ul className="flex flex-col gap-0.5 pl-6 mt-1 border-l-2 border-gray-50 ml-3">
                  {tasks.map(renderTask)}
                </ul>
              )}
            </div>
          );
        })}

        {todos.length === 0 && todoLists.length === 0 && (
          <p className="text-xs text-gray-400 py-4 text-center">No tasks in Microsoft To-Do.</p>
        )}
      </div>
    </div>
  );
}
