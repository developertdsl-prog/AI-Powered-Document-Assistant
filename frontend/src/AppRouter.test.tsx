import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AppRouter from "@/AppRouter";

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  uploadDocument: vi.fn(),
  getDocument: vi.fn(),
  getDocumentText: vi.fn(),
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRouter />
    </MemoryRouter>,
  );
}

describe("application routes", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    ["/documents", "Documents"],
    ["/chat", "Chat"],
    ["/summaries", "Summaries"],
  ])("renders %s", (path, heading) => {
    renderAt(path);
    expect(
      screen.getByRole("heading", { level: 1, name: heading }),
    ).toBeInTheDocument();
  });

  it("renders the dashboard and checks backend health", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ok",
          service: "AI-Powered Document Assistant",
          version: "0.1.0",
          environment: "test",
          database: "up",
        }),
      }),
    );

    renderAt("/");

    expect(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("System status")).toBeInTheDocument();
    expect(await screen.findByText(/v0\.1\.0/)).toBeInTheDocument();
  });

  it("navigates between pages", async () => {
    const user = userEvent.setup();

    renderAt("/documents");
    await user.click(screen.getAllByRole("link", { name: /summaries/i })[0]);

    expect(
      screen.getByRole("heading", { level: 1, name: "Summaries" }),
    ).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", () => {
    renderAt("/does-not-exist");

    expect(
      screen.getByRole("heading", { name: /page not found/i }),
    ).toBeInTheDocument();
  });
});
