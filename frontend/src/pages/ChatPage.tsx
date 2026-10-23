import { Button, PageHeader } from "@/components/ui";
import { EmptyState } from "@/components/ui";
import { MessageSquare, Plus } from "lucide-react";

export default function ChatPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Chat"
        description="Ask questions about a single document or across your library."
        action={
          <Button>
            <Plus className="h-4 w-4" />
            New conversation
          </Button>
        }
      />
      <EmptyState
        icon={MessageSquare}
        title="Document chat coming soon"
        description="Grounded answers with citations will appear here once the retrieval pipeline is ready."
      />
    </div>
  );
}
