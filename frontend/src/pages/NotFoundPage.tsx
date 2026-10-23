import { Button, PageHeader } from "@/components/ui";
import { FileQuestion } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <FileQuestion className="h-7 w-7" />
      </div>
      <PageHeader
        title="Page not found"
        description="The page you are looking for does not exist or has been moved."
        action={<Button onClick={() => window.history.back()}>Go back</Button>}
      />
    </div>
  );
}
