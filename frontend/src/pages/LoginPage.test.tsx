import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/components/auth/AuthProvider";
import LoginPage from "@/pages/LoginPage";
import { ApiError } from "@/services/api";
import { loginAccount } from "@/services/auth";
import type { UserRecord } from "@/types/auth";

vi.mock("@/services/auth", () => ({
  fetchCurrentUser: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
}));

const loginAccountMock = vi.mocked(loginAccount);

const account: UserRecord = {
  id: "user-1",
  email: "ada@example.com",
  full_name: "Ada Lovelace",
  created_at: "2026-11-02T09:42:00Z",
};

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<h1>Dashboard</h1>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function submit(email: string, password: string) {
  const user = userEvent.setup();

  await user.type(screen.getByLabelText(/email/i), email);
  await user.type(screen.getByLabelText(/password/i), password);
  await user.click(screen.getByRole("button", { name: /sign in/i }));

  return user;
}

beforeEach(() => {
  loginAccountMock.mockReset();
  window.localStorage.clear();
});

describe("LoginPage", () => {
  it("asks for credentials when the form is submitted empty", async () => {
    const user = userEvent.setup();

    renderLogin();
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByText(/enter your email and password/i),
    ).toBeInTheDocument();
    expect(loginAccountMock).not.toHaveBeenCalled();
  });

  it("signs in and returns to the page that was requested", async () => {
    loginAccountMock.mockResolvedValue(account);

    renderLogin();
    await submit("  ada@example.com ", "correct-horse");

    // The email is trimmed before it reaches the API.
    expect(loginAccountMock).toHaveBeenCalledWith(
      "ada@example.com",
      "correct-horse",
    );
    expect(
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
  });

  it("shows the backend message when the credentials are rejected", async () => {
    loginAccountMock.mockRejectedValue(
      new ApiError("Incorrect email or password.", 401, "unauthorized"),
    );

    renderLogin();
    await submit("ada@example.com", "wrong-password");

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Incorrect email or password.");
    expect(
      screen.getByRole("heading", { level: 1, name: "Sign in" }),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem("document-assistant-token")).toBeNull();
  });

  it("recovers from an unexpected failure", async () => {
    loginAccountMock.mockRejectedValue(new Error("Backend offline"));

    renderLogin();
    await submit("ada@example.com", "correct-horse");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
  });

  it("allows a retry after a failed attempt", async () => {
    loginAccountMock
      .mockRejectedValueOnce(
        new ApiError("Incorrect email or password.", 401),
      )
      .mockResolvedValueOnce(account);

    renderLogin();
    const user = await submit("ada@example.com", "wrong-password");
    await screen.findByRole("alert");

    // The entered credentials are kept, so the user can simply try again.
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(loginAccountMock).toHaveBeenCalledTimes(2);
  });
});
