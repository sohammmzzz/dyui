import { useState } from "react";
import { Play } from "lucide-react";
import { Bloom } from "../util/motion";
import { optStr, safeMediaUrl } from "../util/props";
import { Skel } from "../util/ui";
import type { DyProps } from "../util/types";
import { BlurImage } from "./Image";
import "../styles/media.css";

type Embed = { provider: "YouTube" | "Vimeo"; src: string; host: string };

/** YouTube / Vimeo URL → privacy-friendly embed URL (loaded only after a click). */
export function toEmbed(url: string): Embed | null {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\.|^m\./, "");
    let id: string | null = null;
    if (host === "youtu.be") id = u.pathname.slice(1).split("/")[0];
    else if (host.endsWith("youtube.com") || host.endsWith("youtube-nocookie.com")) {
      id = u.searchParams.get("v") ?? u.pathname.match(/^\/(?:embed|shorts|live|v)\/([\w-]{6,})/)?.[1] ?? null;
    }
    if (id && /^[\w-]{6,}$/.test(id)) {
      const t = parseInt(u.searchParams.get("t") ?? u.searchParams.get("start") ?? "", 10);
      return {
        provider: "YouTube",
        host: "youtube-nocookie.com",
        src: `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&modestbranding=1&playsinline=1${t > 0 ? `&start=${t}` : ""}`,
      };
    }
    if (host === "vimeo.com" || host === "player.vimeo.com") {
      const vid = u.pathname.match(/(\d{5,})/)?.[1];
      if (vid) return { provider: "Vimeo", host: "player.vimeo.com", src: `https://player.vimeo.com/video/${vid}?autoplay=1&dnt=1` };
    }
  } catch {
    /* ignore */
  }
  return null;
}

/** `video` — native player, or a click-to-load privacy embed for YouTube/Vimeo. */
export function Video({ node }: DyProps) {
  const p = node.props;
  const src = safeMediaUrl(p.src ?? p.url);
  const poster = safeMediaUrl(p.poster);
  const caption = optStr(p.caption);
  const title = optStr(p.title);
  const embed = src ? toEmbed(src) : null;
  const [play, setPlay] = useState(false);
  return (
    <Bloom className="dy-c dy-video" data-dy-ui="video">
      <figure className="dy-image-fig">
        <div className="dy-video-frame">
          {!src ? (
            <Skel className="dy-img-skel" />
          ) : embed ? (
            play ? (
              <iframe
                className="dy-a-fade"
                src={embed.src}
                title={title ?? caption ?? `${embed.provider} video`}
                allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                sandbox="allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox"
              />
            ) : (
              <button type="button" className="dy-video-facade" onClick={() => setPlay(true)} aria-label={`Play ${embed.provider} video${caption ? `: ${caption}` : ""}`}>
                {poster ? <BlurImage src={poster} alt="" cover /> : <span className="dy-video-wash" aria-hidden />}
                <span className="dy-video-play" aria-hidden>
                  <Play width={22} height={22} fill="currentColor" strokeWidth={0} />
                </span>
                <span className="dy-video-note">
                  {embed.provider} · loads from {embed.host} when played
                </span>
              </button>
            )
          ) : (
            <video src={src} poster={poster ?? undefined} controls preload="metadata" playsInline />
          )}
        </div>
        {caption && <figcaption className="dy-media-caption">{caption}</figcaption>}
      </figure>
    </Bloom>
  );
}
