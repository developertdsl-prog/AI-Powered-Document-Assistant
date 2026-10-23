import { Button, PageHeader } from "@/components/ui";
import { EmptyState } from "@/components/ui";
import { Sparkles } from "lucide-react";

export default function SummariesPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Summaries"
        description="Generate concise and detailed summaries with extracted insights."
        action={<Button>Generate summary</Button>}
      />
      <EmptyState
        icon={Sparkles}
        title="Summarization coming soon"
        description="Key points, dates, and structured extractions will be available here."
      />
    </div>
  );
}
