import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { useAuth } from "@/components/auth/AuthContext";
import { clearAuthToken, setAuthToken, handleUnauthorized } from "@/lib/auth";
import { fetchCurrentUser } from "@/services/auth";
import { ApiError } from "@/services/api";
import type { UserRecord } from "@/types/auth";

vi.mock("@/services/auth", () => ({
  fetchCurrentUser: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
}));

const fetchCurrentUserMock = vi.mocked(fetchCurrentUser);

const account: UserRecord = {
  id: "user-1",
  email: "ada@example.com",
  full_name: "Ada Lovelace",
  created_at: "2026-11-02T09:42:00Z",
};

/** Renders a probe so the tests can observe the provider's state. */
function Probe() {
  const { status, user, logout } = useAuth();

  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{user?.email ?? "none"}</p>
      <button type="button" onClick={logout}>
        Sign out
      </button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

beforeEach(() => {
  fetchCurrentUserMock.mockReset();
  clearAuthToken();
});

describe("AuthProvider", () => {
  it("starts anonymous without a stored token", () => {
    renderProvider();

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(fetchCurrentUserMock).not.toHaveBeenCalled();
  });

  it("restores the session from a stored token", async () => {
    setAuthToken("stored-jwt");
    fetchCurrentUserMock.mockResolvedValue(account);

    renderProvider();

    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    expect(await screen.findByTestId("user")).toHaveTextContent(
      "ada@example.com",
    );
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
  });

  it("drops a token the backend rejects with 401", async () => {
    setAuthToken("expired-jwt");
    fetchCurrentUserMock.mockRejectedValue(
      new ApiError("Token expired.", 401, "unauthorized"),
    );

    renderProvider();

    expect(await screen.findByTestId("status")).toHaveTextContent("anonymous");
    // The rejected token must not survive, or the guard would loop.
    expect(localStorage.getItem("document-assistant-token")).toBeNull();
  });

  it("keeps the token when session restore fails on the network", async () => {
    setAuthToken("stored-jwt");
    fetchCurrentUserMock.mockRejectedValue(new Error("Backend offline"));

    renderProvider();

    expect(await screen.findByTestId("status")).toHaveTextContent("anonymous");
    // A transient outage should not sign the user out of the next reload.
    expect(localStorage.getItem("document-assistant-token")).toBe(
      "stored-jwt",
    );
  });

  it("signs out locally", async () => {
    setAuthToken("stored-jwt");
    fetchCurrentUserMock.mockResolvedValue(account);

    renderProvider();
    await screen.findByText("ada@example.com");

    await act(async () => {
      screen.getByRole("button", { name: /sign out/i }).click();
    });

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(localStorage.getItem("document-assistant-token")).toBeNull();
  });

  it("ends the session when a protected request answers 401", async () => {
    setAuthToken("stored-jwt");
    fetchCurrentUserMock.mockResolvedValue(account);

    renderProvider();
    await screen.findByText("ada@example.com");

    await act(async () => {
      handleUnauthorized();
    });

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(localStorage.getItem("document-assistant-token")).toBeNull();
  });
});
