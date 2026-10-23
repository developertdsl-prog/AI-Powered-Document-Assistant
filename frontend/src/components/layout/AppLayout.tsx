import { Outlet } from "react-router-dom";
import { MobileNav, Sidebar } from "./Sidebar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 lg:hidden dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500 text-white">
                <span className="text-sm font-semibold">AI</span>
              </div>
              <p className="text-sm font-semibold">AI-Powered Document Assistant</p>
            </div>
          </header>
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-10">
            <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
              <Outlet />
            </div>
          </main>
          <MobileNav />
        </div>
      </div>
    </div>
  );
}
