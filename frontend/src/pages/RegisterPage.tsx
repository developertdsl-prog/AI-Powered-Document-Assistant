import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { useAuth } from "@/components/auth/AuthContext";
import {
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
} from "@/components/ui";
import { ApiError } from "@/services/api";

interface LocationState {
  from?: { pathname?: string };
}

// Mirrors the backend rules so the common mistakes are caught before a
// round trip: a usable email and a password of at least 8 characters.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MIN_PASSWORD_LENGTH = 8;

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export default function RegisterPage() {
  const { status, register } = useAuth();
  const location = useLocation();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState | null)?.from?.pathname ?? "/";

  if (status === "authenticated") {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();

    if (!trimmedEmail || !password) {
      setError("Enter an email and a password.");
      return;
    }

    if (!EMAIL_PATTERN.test(trimmedEmail)) {
      setError("Enter a valid email address.");
      return;
    }

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    setSubmitting(true);

    try {
      // Registration signs the user in, and the authenticated branch above
      // performs the redirect back to `from`.
      await register({
        email: trimmedEmail,
        password,
        full_name: fullName.trim() || undefined,
      });
    } catch (caught: unknown) {
      setError(describeError(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-950">
      <Card className="w-full max-w-md">
        <CardHeader className="flex flex-col gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500 text-white">
            <UserPlus className="h-5 w-5" />
          </div>
          <div>
            <CardTitle as="h1">Create your account</CardTitle>
            <CardDescription>
              Upload documents and keep your own private library.
            </CardDescription>
          </div>
        </CardHeader>
        <CardBody>
          {/* noValidate keeps the browser's default bubbles out of the way so
              the inline messages below are the only validation the user sees. */}
          <form
            onSubmit={handleSubmit}
            noValidate
            className="flex flex-col gap-4"
          >
            {error ? (
              <div
                role="alert"
                className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300"
              >
                {error}
              </div>
            ) : null}

            <Input
              label="Name"
              type="text"
              name="full_name"
              autoComplete="name"
              placeholder="Ada Lovelace"
              hint="Optional."
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />

            <Input
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />

            <Input
              label="Password"
              type="password"
              name="password"
              autoComplete="new-password"
              hint="At least 8 characters."
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating account..." : "Create account"}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-sky-600 hover:underline dark:text-sky-400"
            >
              Sign in
            </Link>
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
