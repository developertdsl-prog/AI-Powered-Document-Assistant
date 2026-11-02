import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RegisterPage from "@/pages/RegisterPage";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { clearAuthToken } from "@/lib/auth";
import {
  fetchCurrentUser,
  loginAccount,
  registerAccount,
} from "@/services/auth";
import { ApiError } from "@/services/api";
import type { UserRecord } from "@/types/auth";

vi.mock("@/services/auth", () => ({
  fetchCurrentUser: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
}));

const registerAccountMock = vi.mocked(registerAccount);
const loginAccountMock = vi.mocked(loginAccount);

const account: UserRecord = {
  id: "user-1",
  email: "grace@example.com",
  full_name: "Grace Hopper",
  created_at: "2026-10-28T09:00:00Z",
};

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <AuthProvider>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={<p>App home</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  registerAccountMock.mockReset();
  loginAccountMock.mockReset();
  vi.mocked(fetchCurrentUser).mockReset();
  clearAuthToken();
});

describe("RegisterPage", () => {
  it("registers the account and signs the user in", async () => {
    registerAccountMock.mockResolvedValue(account);
    loginAccountMock.mockResolvedValue(account);
    const user = userEvent.setup();

    renderRegister();

    await user.type(
      screen.getByRole("textbox", { name: /name/i }),
      "Grace Hopper",
    );
    await user.type(
      screen.getByRole("textbox", { name: /email/i }),
      "  grace@example.com  ",
    );
    await user.type(screen.getByLabelText(/password/i), "correct-horse");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    await screen.findByText("App home");

    expect(registerAccountMock).toHaveBeenCalledWith({
      email: "grace@example.com",
      password: "correct-horse",
      full_name: "Grace Hopper",
    });
    // The register endpoint issues no token, so AuthProvider signs in right after.
    expect(loginAccountMock).toHaveBeenCalledWith(
      "grace@example.com",
      "correct-horse",
    );
  });

  it("shows the server error when the email is already taken", async () => {
    registerAccountMock.mockRejectedValue(
      new ApiError("That email is already registered.", 409, "conflict"),
    );
    const user = userEvent.setup();

    renderRegister();

    await user.type(
      screen.getByRole("textbox", { name: /email/i }),
      "grace@example.com",
    );
    await user.type(screen.getByLabelText(/password/i), "correct-horse");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email is already registered.",
    );
    expect(loginAccountMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeEnabled();
  });

  it("rejects an invalid email before calling the API", async () => {
    const user = userEvent.setup();

    renderRegister();

    await user.type(
      screen.getByRole("textbox", { name: /email/i }),
      "not-an-email",
    );
    await user.type(screen.getByLabelText(/password/i), "correct-horse");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a valid email address.",
    );
    expect(registerAccountMock).not.toHaveBeenCalled();
  });

  it("rejects a password shorter than 8 characters", async () => {
    const user = userEvent.setup();

    renderRegister();

    await user.type(
      screen.getByRole("textbox", { name: /email/i }),
      "grace@example.com",
    );
    await user.type(screen.getByLabelText(/password/i), "short");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Password must be at least 8 characters.",
    );
    expect(registerAccountMock).not.toHaveBeenCalled();
  });

  it("links to the sign-in page", () => {
    renderRegister();

    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});
