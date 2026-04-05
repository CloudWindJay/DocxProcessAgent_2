function renderInlineSegment(segment, keyPrefix) {
  const parts = segment.split(/(`[^`]+`)/g);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-inline-${index}`;
    if (!part) {
      return null;
    }

    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }

    return <span key={key}>{part}</span>;
  });
}

function renderFormattedText(text) {
  const lines = text.split('\n');

  return lines.map((line, lineIndex) => {
    const boldParts = line.split(/(\*\*[^*]+\*\*)/g);
    const renderedLine = boldParts.map((part, partIndex) => {
      const key = `line-${lineIndex}-part-${partIndex}`;
      if (!part) {
        return null;
      }

      if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
        return <strong key={key}>{renderInlineSegment(part.slice(2, -2), key)}</strong>;
      }

      return <span key={key}>{renderInlineSegment(part, key)}</span>;
    });

    return (
      <span key={`line-${lineIndex}`}>
        {renderedLine}
        {lineIndex < lines.length - 1 ? <br /> : null}
      </span>
    );
  });
}

export default function ChatMessageContent({ content }) {
  return <div className="chat-message-content">{renderFormattedText(content || '')}</div>;
}
