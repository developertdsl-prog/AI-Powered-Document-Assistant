import { NavLink } from "react-router-dom";
import { FileText, Home, LogOut, MessageSquare, Sparkles } from "lucide-react";
import { useAuth } from "@/components/auth/AuthContext";
import { Button } from "@/components/ui";

const navigation = [
  { name: "Dashboard", to: "/", icon: Home },
  { name: "Documents", to: "/documents", icon: FileText },
  { name: "Chat", to: "/chat", icon: MessageSquare },
  { name: "Summaries", to: "/summaries", icon: Sparkles },
];

function linkClassName({ isActive }: { isActive: boolean }) {
  return `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
    isActive
      ? "bg-slate-900 text-white dark:bg-sky-500 dark:text-slate-950"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
  }`;
}

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="hidden w-72 flex-col border-r border-slate-200 bg-white lg:flex dark:border-slate-800 dark:bg-slate-950">
      <div className="flex h-16 items-center gap-2 px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500 text-white">
          <FileText className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            AI Document Assistant
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Document ingestion
          </p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-4">
        {navigation.map((item) => (
          <NavLink key={item.name} to={item.to} className={linkClassName}>
            <item.icon className="h-4 w-4" />
            {item.name}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-4 dark:border-slate-800">
        <div className="min-w-0 px-2">
          <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
            {user?.full_name || user?.email}
          </p>
          {user?.full_name ? (
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {user.email}
            </p>
          ) : null}
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={logout}
          className="justify-start"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}

export function MobileNav() {
  return (
    <nav className="flex items-center justify-around border-t border-slate-200 bg-white px-2 py-1 lg:hidden dark:border-slate-800 dark:bg-slate-950">
      {navigation.map((item) => (
        <NavLink
          key={item.name}
          to={item.to}
          className={({ isActive }) =>
            `flex flex-col items-center gap-1 rounded-lg px-3 py-2 text-xs ${
              isActive
                ? "text-sky-600 dark:text-sky-400"
                : "text-slate-500 dark:text-slate-400"
            }`
          }
        >
          <item.icon className="h-5 w-5" />
          {item.name}
        </NavLink>
      ))}
    </nav>
  );
}
