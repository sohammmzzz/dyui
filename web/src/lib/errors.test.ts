import { describe, expect, it } from "vitest";
import { ApiError, actionFailure, describeError, isInlineSafe } from "./api";

describe("describeError", () => {
  it("413 on upload names the limit", () => {
    expect(describeError(new ApiError("", 413), { kind: "upload", maxUploadMb: 20 })).toBe("That file is too large. The limit is 20 MB.");
    // no known limit: use the server's message when it carries one
    expect(describeError(new ApiError("File is larger than 5 MB.", 413), { kind: "upload" })).toBe("File is larger than 5 MB.");
    expect(describeError(new ApiError("Request is too large.", 413), { kind: "upload" })).toBe("That file is too large to upload.");
  });

  it("413 on a JSON request means the message is too long", () => {
    expect(describeError(new ApiError("Request is too large.", 413), { kind: "message" })).toMatch(/too long/);
    expect(describeError(new ApiError("Request is too large.", 413))).toMatch(/too long/);
  });

  it("429 asks the user to wait", () => {
    expect(describeError(new ApiError("Too many attempts. Try again in a few minutes.", 429), { kind: "login" })).toBe(
      "Too many attempts. Wait a moment and try again.",
    );
  });

  it("401 depends on context", () => {
    expect(describeError(new ApiError("Wrong password.", 401), { kind: "login" })).toBe("Wrong password.");
    expect(describeError(new ApiError("", 401), { kind: "login" })).toMatch(/password/);
    expect(describeError(new ApiError("Password required.", 401))).toMatch(/session has expired/);
  });

  it("409 explains the component was already answered", () => {
    expect(describeError(new ApiError("This has already been answered.", 409))).toBe("This has already been answered.");
    expect(describeError(new ApiError("", 409))).toBe("This was already answered.");
  });

  it("network and unknown errors", () => {
    expect(describeError(new TypeError("Failed to fetch"))).toMatch(/reach the server/);
    expect(describeError(new ApiError("", 503))).toMatch(/server ran into a problem/);
    expect(describeError("weird")).toMatch(/went wrong/);
  });
});

describe("actionFailure", () => {
  it("409 keeps the component resolved with a quiet info toast", () => {
    const plan = actionFailure(new ApiError("This has already been answered.", 409));
    expect(plan).toEqual({ unauthorized: false, keepResolved: true, tone: "info", message: "This has already been answered." });
  });
  it("401 sends the user to the gate", () => {
    expect(actionFailure(new ApiError("", 401)).unauthorized).toBe(true);
  });
  it("other failures undo the optimistic resolution", () => {
    const plan = actionFailure(new ApiError("Unknown action.", 400));
    expect(plan.keepResolved).toBe(false);
    expect(plan.tone).toBe("error");
    expect(plan.message).toBe("Unknown action.");
  });
});

describe("isInlineSafe", () => {
  it("matches the server's inline list; active content downloads", () => {
    for (const t of ["image/png", "image/jpeg", "audio/mpeg", "video/mp4", "application/pdf", "text/plain; charset=utf-8", "application/json"])
      expect(isInlineSafe(t), t).toBe(true);
    for (const t of ["text/html", "image/svg+xml", "application/javascript", "text/javascript", "application/xhtml+xml", "application/octet-stream", "", null])
      expect(isInlineSafe(t), String(t)).toBe(false);
  });
});
