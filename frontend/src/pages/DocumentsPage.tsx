import { Button, PageHeader } from "@/components/ui";
import { EmptyState } from "@/components/ui";
import { FileText, Upload } from "lucide-react";

export default function DocumentsPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Documents"
        description="Upload, manage, and inspect your document library."
        action={
          <Button>
            <Upload className="h-4 w-4" />
            Upload document
          </Button>
        }
      />
      <EmptyState
        icon={FileText}
        title="Document library coming soon"
        description="Uploads, status tracking, and document actions will appear here."
      />
    </div>
  );
}
