const JSON_TO_ZW_INDENT_SPACES = 2;

const formatZwKey = (key: string): string => {
  return key;
};

const convertValueToZw = (
  value: any,
  currentIndentLevel: number
): string => {
  const indent = ' '.repeat(currentIndentLevel * JSON_TO_ZW_INDENT_SPACES);

  if (value === null) {
    return 'null';
  }
  if (typeof value === 'string') {
    // 1. Handle empty string
    if (value === "") {
      return '""'; // Explicitly quoted empty string
    }

    // 2. Handle strings that could be ambiguous if unquoted in ZW
    const lowerVal = value.toLowerCase();
    const isPotentiallyAmbiguous = 
        lowerVal === 'true' || 
        lowerVal === 'false' || 
        lowerVal === 'null' ||
        (value !== "" && !isNaN(Number(value)) && String(Number(value)) === value);

    if (isPotentiallyAmbiguous) {
        return `"${value.replace(/"/g, '\\"')}"`; // Quote it to ensure it's a string
    }
    
    // 3. Handle multi-line strings (strings containing actual newlines)
    if (value.includes('\n')) {
      const lines = value.split('\n');
      return lines.map((line, index) => {
        // The first line is output as is (it's already determined not to need quotes for ambiguity here)
        // Subsequent lines are indented.
        return index === 0 ? line : `${indent}${line}`;
      }).join('\n');
    }

    // 4. Other single-line strings that are not ambiguous
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '[] # Empty list';
    }
    return value.map(item => {
      const itemIndent = ' '.repeat((currentIndentLevel + 1) * JSON_TO_ZW_INDENT_SPACES);
      if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
        // Each object in the list becomes a set of key-value pairs under a '-'
        // The properties of this object are indented relative to the list item itself.
        const itemObjectLines = convertObjectToZwItems(item, currentIndentLevel + 1, true).split('\n');
        // The first line from convertObjectToZwItems for a list item object will be the first key:value
        // It should appear directly after the "- ". Other lines are already indented.
        return `${indent}- ${itemObjectLines.join(`\n${itemIndent}`)}`;
      }
      return `${indent}- ${convertValueToZw(item, currentIndentLevel + 1)}`;
    }).join('\n');
  }
  if (typeof value === 'object' && value !== null) {
    return convertObjectToZwItems(value, currentIndentLevel);
  }
  return String(value); // Fallback
};

const convertObjectToZwItems = (
  obj: Record<string, any>,
  currentIndentLevel: number,
  isChildOfListItem: boolean = false // Indicates if this object is a direct value of a list item object
): string => {
  const indent = ' '.repeat(currentIndentLevel * JSON_TO_ZW_INDENT_SPACES);
  const lines: string[] = [];
  let firstKey = true;

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const value = obj[key];
      const formattedKey = formatZwKey(key);
      
      let lineStartIndent = indent;
      if (isChildOfListItem && firstKey) {
        lineStartIndent = ''; // First key of an object in a list item is not further indented from "-"
      }

      if (typeof value === 'object' && value !== null && (Object.keys(value).length > 0 || (Array.isArray(value) && value.length > 0))) {
        lines.push(`${lineStartIndent}${formattedKey}:`);
        lines.push(convertValueToZw(value, currentIndentLevel + 1));
      } else {
        lines.push(`${lineStartIndent}${formattedKey}: ${convertValueToZw(value, currentIndentLevel)}`);
      }
      firstKey = false;
    }
  }
  return lines.join('\n');
};

export const convertJsonToZwString = (
  jsonString: string,
  rootZwType?: string
): string => {
  let parsedJson: any;
  try {
    parsedJson = JSON.parse(jsonString);
  } catch (error) {
    const err = error as Error;
    return `# Error: Invalid JSON input.\n# ${err.message}`;
  }

  let zwOutput = "";
  const baseIndentLevel = rootZwType && rootZwType.trim() ? 1 : 0;

  if (rootZwType && rootZwType.trim()) {
    zwOutput += `${rootZwType.trim()}:\n`;
  }

  if (typeof parsedJson === 'object' && parsedJson !== null && !Array.isArray(parsedJson)) {
    zwOutput += convertObjectToZwItems(parsedJson, baseIndentLevel);
  } else if (Array.isArray(parsedJson)) {
    const effectiveRootKey = (rootZwType && rootZwType.trim()) ? '' : 'JSON_ARRAY_ROOT:';
    if (!rootZwType) zwOutput += `${effectiveRootKey}\n`;
    
    const arrayIndent = (rootZwType && rootZwType.trim()) ? ' '.repeat(baseIndentLevel * JSON_TO_ZW_INDENT_SPACES) : '';
    // If there is a rootZwType, the array is a value of it.
    // If not, it's the root content itself.
    // The convertValueToZw for array expects to indent its items.
    
    // For a root array with a rootZwType, e.g. ZW-MY-LIST:\n  - item1
    // The list items are children of ZW-MY-LIST.
    // convertValueToZw will generate "- item1", etc. and apply *its own* indentation logic.
    // We need to pass the correct initial indent level for the list items themselves.
    const listItemsOutput = convertValueToZw(parsedJson, baseIndentLevel);
    if (rootZwType && rootZwType.trim()){
      // Output is already indented by convertValueToZw starting from baseIndentLevel for its items.
      // E.g. ZW-ROOT:\n  - item1 (baseIndentLevel for '- item1' is 1)
      zwOutput += listItemsOutput;
    } else {
      // e.g. JSON_ARRAY_ROOT:\n  - item1 (baseIndentLevel for '- item1' is 1)
      zwOutput += listItemsOutput;
    }

  } else { // Root is a primitive value
    const effectiveRootKey = (rootZwType && rootZwType.trim()) ? '' : 'JSON_PRIMITIVE_ROOT:';
     if (!rootZwType) zwOutput += `${effectiveRootKey}\n`;
    
    const primitiveIndent = ' '.repeat(baseIndentLevel * JSON_TO_ZW_INDENT_SPACES);
    zwOutput += `${primitiveIndent}ROOT_VALUE: ${convertValueToZw(parsedJson, 0)}`;
  }

  return zwOutput.trim() === "" && rootZwType && rootZwType.trim() ? `${rootZwType.trim()}:` : zwOutput;
};