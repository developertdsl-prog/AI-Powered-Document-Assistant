import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AppRouter from "@/AppRouter";
import { ApiError } from "@/services/api";
import { fetchCurrentUser, loginAccount } from "@/services/auth";
import type { UserRecord } from "@/types/auth";

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  getDocument: vi.fn(),
  getDocumentText: vi.fn(),
}));

vi.mock("@/services/conversations", () => ({
  listConversations: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));

vi.mock("@/services/auth", () => ({
  fetchCurrentUser: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
}));

const fetchCurrentUserMock = vi.mocked(fetchCurrentUser);
const loginAccountMock = vi.mocked(loginAccount);

const currentUser: UserRecord = {
  id: "user-1",
  email: "ada@example.com",
  full_name: "Ada Lovelace",
  created_at: "2026-10-23T09:42:00Z",
};

const TOKEN_KEY = "document-assistant-token";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRouter />
    </MemoryRouter>,
  );
}

/** Store a token so the provider restores a session instead of staying anonymous. */
function signIn() {
  window.localStorage.setItem(TOKEN_KEY, "signed-in-token");
  fetchCurrentUserMock.mockResolvedValue(currentUser);
}

describe("application routes", () => {
  beforeEach(() => {
    window.localStorage.clear();
    fetchCurrentUserMock.mockReset();
    loginAccountMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it.each([
    ["/documents", "Documents"],
    ["/chat", "Chat"],
    ["/summaries", "Summaries"],
  ])("renders %s", async (path, heading) => {
    signIn();

    renderAt(path);

    expect(
      await screen.findByRole("heading", { level: 1, name: heading }),
    ).toBeInTheDocument();
  });

  it("renders the dashboard and checks backend health", async () => {
    signIn();
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
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("System status")).toBeInTheDocument();
    expect(await screen.findByText(/v0\.1\.0/)).toBeInTheDocument();
  });

  it("navigates between pages", async () => {
    signIn();
    const user = userEvent.setup();

    renderAt("/documents");
    await screen.findByRole("heading", { level: 1, name: "Documents" });

    await user.click(screen.getAllByRole("link", { name: /summaries/i })[0]);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Summaries" }),
    ).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", async () => {
    renderAt("/does-not-exist");

    expect(
      await screen.findByRole("heading", { name: /page not found/i }),
    ).toBeInTheDocument();
  });

  // --- authentication ------------------------------------------------------

  it("sends anonymous visitors to the sign in page", async () => {
    renderAt("/documents");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sign in" }),
    ).toBeInTheDocument();
    expect(fetchCurrentUserMock).not.toHaveBeenCalled();
  });

  it("signs in and returns to the page that was requested", async () => {
    loginAccountMock.mockResolvedValue(currentUser);
    const user = userEvent.setup();

    renderAt("/documents");
    await screen.findByRole("heading", { level: 1, name: "Sign in" });

    await user.type(screen.getByLabelText(/email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-horse");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(loginAccountMock).toHaveBeenCalledWith(
      "ada@example.com",
      "correct-horse",
    );
    expect(
      await screen.findByRole("heading", { level: 1, name: "Documents" }),
    ).toBeInTheDocument();
  });

  it("ends the session when the stored token is rejected", async () => {
    window.localStorage.setItem(TOKEN_KEY, "expired-token");
    fetchCurrentUserMock.mockRejectedValue(
      new ApiError("The token is invalid or has expired.", 401, "unauthorized"),
    );

    renderAt("/");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sign in" }),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("keeps the stored token when the session check cannot reach the API", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    fetchCurrentUserMock.mockRejectedValue(new Error("Backend offline"));

    renderAt("/");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sign in" }),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("stored-token");
  });
});
