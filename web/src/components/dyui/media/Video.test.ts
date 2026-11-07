import { describe, expect, it } from "vitest";
import { toEmbed } from "./Video";

describe("toEmbed", () => {
  it("embeds real YouTube / Vimeo URLs via the privacy hosts", () => {
    expect(toEmbed("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42")?.src).toBe(
      "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0&modestbranding=1&playsinline=1&start=42",
    );
    expect(toEmbed("https://youtu.be/dQw4w9WgXcQ")?.provider).toBe("YouTube");
    expect(toEmbed("https://m.youtube.com/shorts/dQw4w9WgXcQ")?.provider).toBe("YouTube");
    expect(toEmbed("https://vimeo.com/123456789")?.src).toBe("https://player.vimeo.com/video/123456789?autoplay=1&dnt=1");
  });

  it("rejects look-alike hosts and non-http schemes", () => {
    for (const url of [
      "https://evilyoutube.com/watch?v=dQw4w9WgXcQ",
      "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
      "https://notyoutube-nocookie.com/embed/dQw4w9WgXcQ",
      "https://evilvimeo.com/123456789",
      "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    ]) {
      expect(toEmbed(url), url).toBeNull();
    }
  });

  it("never lets the video id break out of the embed URL", () => {
    expect(toEmbed('https://www.youtube.com/watch?v=abc"><script>')).toBeNull();
    expect(toEmbed("https://www.youtube.com/watch?v=abcdefg%26autoplay%3D0")).toBeNull();
  });
});
