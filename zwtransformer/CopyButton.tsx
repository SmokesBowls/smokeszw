import React, { useState } from 'react';

interface CopyButtonProps {
  textToCopy: string;
  buttonText?: string;
  copiedText?: string;
  className?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
}

const CopyButton: React.FC<CopyButtonProps> = ({
  textToCopy,
  buttonText = 'Copy All',
  copiedText = 'Copied!',
  className = 'copy-button',
  style,
  disabled = false,
}) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    if (!navigator.clipboard) {
      // Fallback for older browsers or non-secure contexts (though less common now)
      console.warn('Clipboard API not available.');
      alert('Copying to clipboard is not supported in this browser or context.');
      return;
    }
    if (!textToCopy) {
        // Nothing to copy, or button should be disabled
        return;
    }

    try {
      await navigator.clipboard.writeText(textToCopy);
      setIsCopied(true);
      setTimeout(() => {
        setIsCopied(false);
      }, 1500); // Reset after 1.5 seconds
    } catch (err) {
      console.error('Failed to copy text: ', err);
      alert('Failed to copy text. See console for details.');
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={className}
      style={style}
      disabled={disabled || !textToCopy}
      title={disabled || !textToCopy ? "Nothing to copy" : "Copy content to clipboard"}
    >
      {isCopied ? copiedText : buttonText}
    </button>
  );
};

export default CopyButton;
