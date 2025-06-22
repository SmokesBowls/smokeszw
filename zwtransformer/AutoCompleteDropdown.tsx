import React from 'react';

interface AutoCompleteDropdownProps {
  suggestions: string[];
  show: boolean;
  activeIndex: number;
  onSelectSuggestion: (suggestion: string) => void;
  position: { top: number; left: number }; // For positioning
}

const AutoCompleteDropdown: React.FC<AutoCompleteDropdownProps> = ({
  suggestions,
  show,
  activeIndex,
  onSelectSuggestion,
  position,
}) => {
  if (!show || suggestions.length === 0) {
    return null;
  }

  return (
    <div
      className="autocomplete-dropdown"
      style={{
        top: `${position.top}px`,
        left: `${position.left}px`,
      }}
      role="listbox"
      aria-label="ZW Auto-completion suggestions"
    >
      <ul>
        {suggestions.map((suggestion, index) => (
          <li
            key={suggestion}
            className={index === activeIndex ? 'active-suggestion' : ''}
            onClick={() => onSelectSuggestion(suggestion)}
            onMouseEnter={(e) => {
                // Optional: update activeIndex on mouse hover if desired for mixed mouse/keyboard interaction
                // This might require passing a setter for activeIndex if not managed by parent on hover
            }}
            role="option"
            aria-selected={index === activeIndex}
            id={`suggestion-${index}`} // For aria-activedescendant
          >
            {suggestion}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AutoCompleteDropdown;
