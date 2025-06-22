
export interface ZWNode {
  key: string;
  value?: string | ZWNode[] | ZWListItem[];
  depth: number;
  parent?: ZWNode; 
  delimiter?: string; // Store the delimiter used for this node's children if applicable
}

export interface ZWListItem {
  value: string | ZWNode[];
  isKeyValue?: boolean;
  itemKey?: string;
  depth: number;
  delimiter?: string; // Store the delimiter if it's a list of KVs
}

const getIndentation = (line: string): number => {
  const match = line.match(/^(\s*)/);
  return match ? match[0].length : 0;
};

const escapeRegExp = (string: string): string => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
};

export const parseZW = (zwString: string, options?: { delimiter?: string }): ZWNode | null => {
  let processedZwString = zwString.trim();

  // Check for common markdown code fences and strip them
  // Handles fences like ```zw ... ``` or ``` ... ```
  const codeFenceRegex = /^```(?:[a-zA-Z0-9_-]+)?\s*\n?([\s\S]*?)\s*\n?```$/;
  const fenceMatch = processedZwString.match(codeFenceRegex);
  if (fenceMatch && fenceMatch[1]) {
    processedZwString = fenceMatch[1].trim(); 
  }

  if (!processedZwString) {
    return null;
  }

  const semanticLines = processedZwString.split('\n').filter(line => {
    const trimmed = line.trim();
    return trimmed !== '' && !trimmed.startsWith('#');
  });

  if (semanticLines.length === 0) return null;

  const rootLineContent = semanticLines[0];
  // Regex means the line MUST be "TYPE:" and nothing else after the colon (except whitespace).
  const rootLineRegex = /^([A-Z0-9_-]+(?:-[A-Z0-9_-]+)*):\s*$/i; 
  const rootMatch = rootLineContent.match(rootLineRegex);

  if (!rootMatch) {
    return { 
      key: 'Error: Invalid Root', 
      value: `Packet must start with a ZW Type declaration on its own line (e.g., ZW-REQUEST:). The first significant line found was: "${rootLineContent.substring(0, 70)}${rootLineContent.length > 70 ? '...' : ''}". It did not match the expected format. Common issues: text after the colon on the root line, or missing root type.`, 
      depth: 0 
    };
  }
  
  const effectiveDelimiter = options?.delimiter || ':';
  const escapedDelimiter = escapeRegExp(effectiveDelimiter);

  const rootNode: ZWNode = { key: rootMatch[1], value: [], depth: 0, delimiter: effectiveDelimiter };
  const stack: Array<ZWNode> = [rootNode];

  // Regexes using the effective delimiter for children
  const sectionRegex = new RegExp(`^([A-Za-z0-9_]+)${escapedDelimiter}\\s*$`);
  const keyValueRegex = new RegExp(`^([A-Za-z0-9_]+)${escapedDelimiter}\\s*(.*)$`);


  for (let i = 1; i < semanticLines.length; i++) {
    const line = semanticLines[i];
    const trimmedLine = line.trim();
    const currentIndent = getIndentation(line);
    // Assuming 2 spaces for indentation depth, adjust if ZW spec allows others
    const depth = Math.max(1, currentIndent / 2); 

    while (stack.length > 1) {
        const currentParentOnStack = stack[stack.length - 1];
        if (depth > currentParentOnStack.depth) {
            break; 
        }
        stack.pop();
    }
    
    const parentNode = stack[stack.length - 1];
    // Ensure parentNode.value is initialized as an array if it's meant to hold children
    if (parentNode.value === undefined || typeof parentNode.value === 'string') {
        parentNode.value = [];
    }


    if (trimmedLine.startsWith('- ')) {
      const itemContent = trimmedLine.substring(2).trim();
      if (!Array.isArray(parentNode.value)) {
         console.warn("Parent node value is not an array for list item:", parentNode);
         parentNode.value = [];
      }
      
      const listItem: ZWListItem = { value: itemContent, depth: depth, delimiter: effectiveDelimiter };
      // Regex for key-value list items, also uses the effectiveDelimiter
      const listItemKvRegex = new RegExp(`^([A-Za-z0-9_]+)${escapedDelimiter}\\s*(.*)$`);
      const kvMatch = itemContent.match(listItemKvRegex);

      if(kvMatch){
        listItem.isKeyValue = true;
        listItem.itemKey = kvMatch[1];
        listItem.value = kvMatch[2] || ''; 
      }
      (parentNode.value as ZWListItem[]).push(listItem);

    } else {
      const sectionMatch = trimmedLine.match(sectionRegex); 
      const keyValueMatch = trimmedLine.match(keyValueRegex);

      if (!Array.isArray(parentNode.value)) {
         console.warn("Parent node value is not an array for node item:", parentNode);
         parentNode.value = [];
      }

      if (sectionMatch) { 
        const newNode: ZWNode = { key: sectionMatch[1], value: [], depth: depth, delimiter: effectiveDelimiter };
        (parentNode.value as ZWNode[]).push(newNode);
        stack.push(newNode);
      } else if (keyValueMatch) { 
        const newNode: ZWNode = { key: keyValueMatch[1], value: keyValueMatch[2] || '', depth: depth, delimiter: effectiveDelimiter };
        (parentNode.value as ZWNode[]).push(newNode);
      } else if (trimmedLine && Array.isArray(parentNode.value) && parentNode.value.length > 0) {
          // Handling multi-line string values for the last item
          const lastChild = parentNode.value[parentNode.value.length - 1];
          
          if (lastChild && typeof lastChild.value === 'string') { 
             (lastChild.value as string) += `\n${line.substring(currentIndent)}`; // Preserve relative indent for multiline
          } else {
            // console.warn(`Unhandled line in ZW parsing: "${trimmedLine}" under parent:`, parentNode.key);
          }
      } else if (trimmedLine) {
        // console.warn(`Orphaned line in ZW parsing: "${trimmedLine}"`);
      }
    }
  }
  return rootNode;
};

export function validateZWContent(content: string): boolean {
  try {
    const parsed = parseZW(content);
    return parsed !== null;
  } catch {
    return false;
  }
}
