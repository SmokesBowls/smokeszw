
import { ZWNode, ZWListItem } from './zwParser';

const escapeGdScriptString = (str: string): string => {
  // Escapes backslashes and double quotes for GDScript strings.
  return `"${str.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
};

const formatGodotKey = (key: string): string => {
  // Formats a ZW key as a GDScript dictionary key (string).
  return escapeGdScriptString(key);
};

const convertNodeValueToGodot = (
  nodeValue: ZWNode['value'] | ZWListItem['value'],
  indentLevel: number
): string => {
  const indent = '  '.repeat(indentLevel);
  const nextIndent = '  '.repeat(indentLevel + 1);

  if (typeof nodeValue === 'string') {
    return escapeGdScriptString(nodeValue);
  }

  if (Array.isArray(nodeValue)) {
    if (nodeValue.length === 0) {
      // An empty array from ZWNode value (section) implies an empty dictionary.
      // An empty array from ZWListItem value (list item) implies an empty list.
      // This heuristic depends on context, but for now, if nodeValue is ZWNode[], it's dict.
      // If it's ZWListItem[], it's list. The parser ensures this distinction.
      // The first item check below clarifies.
      const isLikelyFromListNode = nodeValue.length > 0 && !('key' in nodeValue[0]); // Check if elements are ZWListItems
      return isLikelyFromListNode ? '[]' : '{}';
    }

    const firstItem = nodeValue[0];

    // Check if it's an array of ZWListItems (forming a GDScript Array)
    // ZWListItem does not have 'key', ZWNode does.
    if (!('key' in firstItem) || 'itemKey' in firstItem) {
      const listItems = (nodeValue as ZWListItem[]).map(listItem => {
        if (listItem.isKeyValue && listItem.itemKey) {
          // List item is a Key-Value pair, render as a dictionary within the list
          return `${nextIndent}{ ${formatGodotKey(listItem.itemKey)}: ${convertNodeValueToGodot(listItem.value, indentLevel + 1)} }`;
        }
        // Otherwise, it's a simple value or a nested structure within the list item
        return `${nextIndent}${convertNodeValueToGodot(listItem.value, indentLevel + 1)}`;
      });
      return `[\n${listItems.join(',\n')}\n${indent}]`;
    }
    // Else, it's an array of ZWNodess (children of a section, forming a GDScript Dictionary)
    else {
      const dictEntries = (nodeValue as ZWNode[]).map(childNode =>
        `${nextIndent}${formatGodotKey(childNode.key)}: ${convertNodeValueToGodot(childNode.value, indentLevel + 1)}`
      );
      return `{\n${dictEntries.join(',\n')}\n${indent}}`;
    }
  }

  // If nodeValue is undefined (e.g. a ZW section with no children like "SECTION:")
  if (nodeValue === undefined) {
    return '{}'; // Represent as an empty dictionary
  }
  
  return 'null'; // Fallback for unexpected types, though parser should prevent this.
};

export const convertZwToGodot = (rootNode: ZWNode | null): string => {
  if (!rootNode || rootNode.key.startsWith('Error:')) {
    return `# Error: Invalid ZW input or parsing failed.\n# Message: ${rootNode?.key || 'Unknown error'} ${typeof rootNode?.value === 'string' ? rootNode.value : ''}`;
  }

  // Convert ZW_ROOT_TYPE to ZW_ROOT_TYPE for GDScript variable name
  const godotVariableName = rootNode.key.replace(/-/g, '_').toUpperCase();
  let gdScriptString = `# Auto-generated GDScript from ZW template: ${rootNode.key}\n`;
  gdScriptString += `var ${godotVariableName} = `;

  // rootNode.value from parser is expected to be ZWNode[] or ZWListItem[] if it has children,
  // or undefined if it's just "ZW-TYPE:"
  if (rootNode.value === undefined) {
     gdScriptString += "{}\n# Root node was a simple declaration without children.";
  } else if (Array.isArray(rootNode.value)) {
    if (rootNode.value.length === 0) {
        gdScriptString += "{}\n# Root node has no children defined.";
    } else {
        // Determine if rootNode.value represents a list or a dictionary structure
        const firstChild = rootNode.value[0];
        if (!('key' in firstChild) || 'itemKey' in firstChild) { // Indicates ZWListItem array (list)
            gdScriptString += convertNodeValueToGodot(rootNode.value, 0); // Start indentLevel at 0 for root list
        } else { // Indicates ZWNode array (dictionary)
            gdScriptString += convertNodeValueToGodot(rootNode.value, 0); // Start indentLevel at 0 for root dictionary
        }
    }
  } else if (typeof rootNode.value === 'string') {
    // This case (e.g., "ZW-ROOT: some_string_value") is unusual for a root packet,
    // as ZW parser structure typically makes rootNode.value an array or undefined.
    // However, if it occurs, export the string value directly.
    gdScriptString += `${escapeGdScriptString(rootNode.value)};\n# Root node had a direct string value.`;
  } else {
    gdScriptString += "{}\n# Root node had an unexpected structure or no parsable children.";
  }

  gdScriptString += "\n";
  return gdScriptString;
};
