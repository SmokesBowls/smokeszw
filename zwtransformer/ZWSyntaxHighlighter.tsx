import React from 'react';

interface ZWSyntaxHighlighterProps {
  zwString: string;
}

const ZWSyntaxHighlighter: React.FC<ZWSyntaxHighlighterProps> = ({ zwString }) => {
  if (!zwString || zwString.trim() === '') {
    return <p style={{ color: '#7f8c8d', padding: '10px', fontFamily: "'Courier New', Courier, monospace", fontSize: '0.9em' }}>Define ZW template to see highlighted syntax...</p>;
  }

  const lines = zwString.split('\n');

  const highlightLine = (line: string): JSX.Element => {
    // 1. Comment (matches entire line if it starts with optional spaces then #)
    const commentMatch = line.match(/^(\s*#.*)$/);
    if (commentMatch) {
      return <span className="zw-comment">{line}</span>;
    }

    // 2. Root Type (e.g., ZW-TYPE:)
    const rootTypeMatch = line.match(/^(\s*)([A-Z0-9_-]+(?:-[A-Z0-9_-]+)*:)(\s*)$/i);
    if (rootTypeMatch) {
      return <>{rootTypeMatch[1]}<span className="zw-type">{rootTypeMatch[2]}</span>{rootTypeMatch[3]}</>;
    }
    
    // 3. List item with Key-Value (e.g., "  - Key: Value") - must be checked before simple list item
    const listItemKvMatch = line.match(/^(\s*)(- )([A-Za-z0-9_]+:)(\s*)(.*)$/);
    if (listItemKvMatch) {
      return <>{listItemKvMatch[1]}<span className="zw-list-marker">{listItemKvMatch[2]}</span><span className="zw-key">{listItemKvMatch[3]}</span>{listItemKvMatch[4]}<span className="zw-value">{listItemKvMatch[5]}</span></>;
    }

    // 4. Simple List Item (e.g., "  - Value")
    const listItemMatch = line.match(/^(\s*)(- )(.+)$/);
    if (listItemMatch) {
      return <>{listItemMatch[1]}<span className="zw-list-marker">{listItemMatch[2]}</span><span className="zw-value">{listItemMatch[3]}</span></>;
    }
    
    // 5. Section (e.g., "  SECTIONNAME:")
    const sectionMatch = line.match(/^(\s*)([A-Za-z0-9_]+:)(\s*)$/);
    if (sectionMatch) {
      return <>{sectionMatch[1]}<span className="zw-section">{sectionMatch[2]}</span>{sectionMatch[3]}</>;
    }

    // 6. Key-Value pair (e.g., "  Key: Value")
    const keyValueMatch = line.match(/^(\s*)([A-Za-z0-9_]+:)(\s*)(.*)$/);
    if (keyValueMatch) {
      return <>{keyValueMatch[1]}<span className="zw-key">{keyValueMatch[2]}</span>{keyValueMatch[3]}<span className="zw-value">{keyValueMatch[4]}</span></>;
    }
    
    // Default: plain text (no specific class, will inherit container style)
    return <>{line}</>;
  };

  return (
    <div className="zw-syntax-highlight" aria-live="polite" aria-label="Syntax highlighted ZW template preview">
      {lines.map((line, index) => (
        <div key={index} className="zw-line">
          {highlightLine(line)}
        </div>
      ))}
    </div>
  );
};

export default ZWSyntaxHighlighter;