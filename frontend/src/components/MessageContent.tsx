import { Typography } from "antd";

type Segment =
  | { type: "code"; content: string }
  | { type: "paragraph"; content: string }
  | { type: "heading"; content: string }
  | { type: "list"; items: string[] };

function parseContent(content: string): Segment[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const segments: Segment[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let codeLines: string[] = [];
  let inCode = false;

  const flushParagraph = () => {
    if (paragraph.length) {
      segments.push({ type: "paragraph", content: paragraph.join(" ").trim() });
      paragraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length) {
      segments.push({ type: "list", items: listItems });
      listItems = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith("```")) {
      if (inCode) {
        segments.push({ type: "code", content: codeLines.join("\n") });
        codeLines = [];
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(rawLine);
      continue;
    }

    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    if (/^#{1,4}\s+/.test(line)) {
      flushParagraph();
      flushList();
      segments.push({ type: "heading", content: line.replace(/^#{1,4}\s+/, "") });
      continue;
    }

    const bulletMatch = line.match(/^[-*]\s+(.+)$/) ?? line.match(/^\d+\.\s+(.+)$/);
    if (bulletMatch) {
      flushParagraph();
      listItems.push(bulletMatch[1]);
      continue;
    }

    paragraph.push(line);
  }

  if (inCode) {
    segments.push({ type: "code", content: codeLines.join("\n") });
  }
  flushParagraph();
  flushList();
  return segments.length ? segments : [{ type: "paragraph", content }];
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

export function MessageContent({ content }: { content: string }) {
  return (
    <div className="message-content">
      {parseContent(content).map((segment, index) => {
        if (segment.type === "heading") {
          return (
            <Typography.Title key={index} level={5} className="message-heading">
              {renderInline(segment.content)}
            </Typography.Title>
          );
        }
        if (segment.type === "list") {
          return (
            <ul key={index} className="message-list-block">
              {segment.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        if (segment.type === "code") {
          return (
            <pre key={index} className="message-code-block">
              <code>{segment.content}</code>
            </pre>
          );
        }
        return (
          <Typography.Paragraph key={index} className="message-paragraph">
            {renderInline(segment.content)}
          </Typography.Paragraph>
        );
      })}
    </div>
  );
}
