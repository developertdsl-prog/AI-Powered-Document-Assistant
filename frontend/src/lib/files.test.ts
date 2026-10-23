import { describe, expect, it } from "vitest";
import {
  MAX_UPLOAD_BYTES,
  documentTypeLabel,
  formatFileSize,
  validateFile,
} from "./files";

function fileOf(name: string, content = "hello", type = "text/plain"): File {
  return new File([content], name, { type });
}

describe("validateFile", () => {
  it.each(["report.pdf", "REQUIREMENTS.DOCX", "notes.txt"])(
    "accepts %s",
    (name) => {
      expect(validateFile(fileOf(name))).toBeNull();
    },
  );

  it("rejects unsupported extensions", () => {
    expect(validateFile(fileOf("photo.png", "x", "image/png"))).toContain(
      "Unsupported format",
    );
  });

  it("rejects files without an extension", () => {
    expect(validateFile(fileOf("README"))).toContain("Unsupported format");
  });

  it("rejects empty files", () => {
    expect(validateFile(new File([], "empty.txt"))).toContain("empty");
  });

  it("rejects files over the size limit", () => {
    const file = fileOf("large.pdf", "x", "application/pdf");
    Object.defineProperty(file, "size", {
      value: MAX_UPLOAD_BYTES + 1,
    });

    expect(validateFile(file)).toContain("maximum upload size");
  });
});

describe("formatFileSize", () => {
  it.each([
    [512, "512 B"],
    [18 * 1024, "18 KB"],
    [412 * 1024, "412 KB"],
    [2.4 * 1024 * 1024, "2.4 MB"],
    [20 * 1024 * 1024, "20 MB"],
  ])("formats %d bytes as %s", (bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});

describe("documentTypeLabel", () => {
  it("derives the label from the extension", () => {
    expect(documentTypeLabel("report.pdf")).toBe("PDF");
    expect(documentTypeLabel("notes.TXT")).toBe("TXT");
    expect(documentTypeLabel("archive.zip")).toBe("FILE");
  });
});
