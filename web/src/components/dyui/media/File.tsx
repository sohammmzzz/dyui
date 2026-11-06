import { Download, File as FileIcon, FileArchive, FileAudio, FileCode2, FileImage, FileSpreadsheet, FileText, FileVideo } from "lucide-react";
import { Bloom } from "../util/motion";
import { formatBytes, optStr, safeUrl, str } from "../util/props";
import { Skel } from "../util/ui";
import { isFileUrl } from "../../../lib/url";
import type { DyProps } from "../util/types";
import "../styles/media.css";

function kindOf(name: string, type?: string) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  const t = (type || "").toLowerCase();
  if (t.startsWith("image/") || ["png", "jpg", "jpeg", "gif", "webp", "svg", "avif", "heic"].includes(ext)) return { Icon: FileImage, tone: "teal" };
  if (t.startsWith("audio/") || ["mp3", "wav", "m4a", "ogg", "flac"].includes(ext)) return { Icon: FileAudio, tone: "rose" };
  if (t.startsWith("video/") || ["mp4", "mov", "webm", "mkv"].includes(ext)) return { Icon: FileVideo, tone: "rose" };
  if (["zip", "tar", "gz", "rar", "7z"].includes(ext) || t.includes("zip")) return { Icon: FileArchive, tone: "amber" };
  if (["csv", "xls", "xlsx", "numbers", "tsv"].includes(ext) || t.includes("spreadsheet") || t.includes("csv")) return { Icon: FileSpreadsheet, tone: "green" };
  if (["py", "js", "ts", "tsx", "json", "html", "css", "go", "rs", "java", "rb", "sh", "yaml", "yml", "toml", "sql"].includes(ext)) return { Icon: FileCode2, tone: "blue" };
  if (["pdf", "doc", "docx", "txt", "md", "rtf", "pages"].includes(ext) || t.includes("pdf") || t.startsWith("text/")) return { Icon: FileText, tone: ext === "pdf" ? "red" : "accent" };
  return { Icon: FileIcon, tone: "accent" };
}

/** `file` — a download card. */
export function File({ node }: DyProps) {
  const p = node.props;
  const name = str(p.name) || "Download";
  const url = safeUrl(p.url);
  const size = formatBytes(p.size);
  const type = optStr(p.type);
  const ext = (name.includes(".") ? name.split(".").pop() : "")?.toUpperCase();
  const { Icon, tone } = kindOf(name, type);
  const meta = [ext || type, size].filter(Boolean).join(" · ");
  const streaming = node.status === "streaming";
  const inner = (
    <>
      <span className="dy-file-icon" data-tone={tone} aria-hidden>
        <Icon width={19} height={19} strokeWidth={1.8} />
      </span>
      <span className="dy-file-main">
        <span className="dy-file-name dy-ellipsis">{p.name ? name : <Skel w={140} h={10} />}</span>
        <span className="dy-file-meta">{meta || (streaming ? <Skel w={70} h={8} /> : "File")}</span>
      </span>
      {url && (
        <span className="dy-file-dl" aria-hidden>
          <Download width={16} height={16} />
        </span>
      )}
    </>
  );
  return (
    <Bloom className="dy-c dy-file-wrap" data-dy-ui="file">
      {url ? (
        <a
          className="dy-file dy-panel"
          href={url}
          // the app's own files download in place; external URLs open in a new tab
          {...(isFileUrl(p.url) ? {} : { target: "_blank", rel: "noopener noreferrer" })}
          download={name}
          aria-label={`Download ${name}${meta ? ` (${meta})` : ""}`}>
          {inner}
        </a>
      ) : (
        <div className="dy-file dy-panel" data-disabled="">
          {inner}
        </div>
      )}
    </Bloom>
  );
}
