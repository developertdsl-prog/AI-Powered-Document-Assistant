import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "@/components/ui/Button";

describe("Button", () => {
  it("renders with primary styles", () => {
    render(<Button>Upload</Button>);
    const button = screen.getByRole("button", { name: /upload/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass("bg-slate-900");
  });
});
