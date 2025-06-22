import { ZWNode, ZWListItem, parseZW } from './zwParser';

// Helper to infer JSON value types from ZW string values
const inferJsonValue = (valStr: string | undefined): any => {
    if (valStr === undefined) return undefined; // Represent undefined ZW values as undefined in JS object

    const trimmedVal = valStr.trim();

    if (trimmedVal.toLowerCase() === 'true') return true;
    if (trimmedVal.toLowerCase() === 'false') return false;
    if (trimmedVal.toLowerCase() === 'null') return null;

    // Check if it's a number
    if (trimmedVal !== "" && !isNaN(Number(trimmedVal))) {
         // Ensure that the string itself is a valid representation of that number
        if (String(Number(trimmedVal)) === trimmedVal) {
            return Number(trimmedVal);
        }
    }
    
    // Handle explicitly double-quoted strings in ZW
    if (trimmedVal.length >= 2 && trimmedVal.startsWith('"') && trimmedVal.endsWith('"')) {
        return trimmedVal.substring(1, trimmedVal.length - 1).replace(/\\"/g, '"');
    }
    // Handle explicitly single-quoted strings in ZW
    if (trimmedVal.length >= 2 && trimmedVal.startsWith("'") && trimmedVal.endsWith("'")) {
        return trimmedVal.substring(1, trimmedVal.length - 1).replace(/\\'/g, "'");
    }

    // Otherwise, it's an unquoted string value from ZW
    return trimmedVal; 
};

// Recursive function to convert ZWNode/ZWListItem values to JSON values/structures
const convertZwValueToJson = (value: ZWNode['value'] | ZWListItem['value']): any => {
    if (typeof value === 'string') {
        return inferJsonValue(value);
    }

    if (value === undefined) { // An empty ZW section (e.g., SECTION:)
        return {}; // Represents an empty JSON object for that section
    }

    if (Array.isArray(value)) {
        if (value.length === 0) {
            // If parseZW gives `value: []` for `SECTION: \n # no children`, it becomes `SECTION_KEY: {}`
            // If `value: []` for `LIST_KEY:\n  # no items` (where items would be ZWListItems), it becomes `LIST_KEY: []`
            // This function is generic. The distinction often relies on the type of items if the array wasn't empty.
            // Given an empty array, it's ambiguous without more context whether it should be {} or [].
            // However, if `parseZW` ensures `value` is `[]` for a section KEY that has no children,
            // then for that KEY, its value should be `{}`.
            // If `value` is `[]` for a list KEY that has no items, its value should be `[]`.
            // Let's assume for now, if an Array of ZWNode is passed, and it's empty, it means empty object.
            // If an Array of ZWListItem is passed, and it's empty, it means empty array.
            // This function receives the `value` property. The type of children must be inferred if possible.
            // The caller (convertZwToJsonObject) will handle the root.value. If root.value itself is an empty array of ZWNode,
            // it means the root object is empty. If root.value is an empty array of ZWListItem, the root object should contain an empty list.
            // For now, let's default to {} if items are ZWNodess and [] if items are ZWListItems, which is decided by the first item check.
            // If the array is truly empty, we can't check the first item.
            // parseZW's structure: ZWNode.value can be ZWNode[] or ZWListItem[]. ZWListItem.value can be string or ZWNode[].
            // If value is [], and it's for a ZWNode, it means no children for that node, so its JSON value is {}.
            return {}; // Defaulting to object for an empty structure. If it was meant to be a list, the parent ZWNode should indicate that.
        }

        const firstItem = value[0];

        if (firstItem && (!('key' in firstItem) || 'itemKey' in firstItem)) { // Heuristic for ZWListItem array
            return value.map(item => {
                const listItem = item as ZWListItem;
                if (listItem.isKeyValue && listItem.itemKey) {
                    // Value of a list item that is a KV pair (e.g. - NAME: Eva)
                    return { [listItem.itemKey]: convertZwValueToJson(listItem.value) };
                }
                // Value of a simple list item (e.g. - item1 or - SECTION_IN_LIST:)
                return convertZwValueToJson(listItem.value); 
            });
        }
        else if (firstItem && 'key' in firstItem) { // Assumed to be ZWNode[] (children of a ZW section)
            const obj: Record<string, any> = {};
            for (const item of value) {
                const node = item as ZWNode;
                obj[node.key] = convertZwValueToJson(node.value);
            }
            return obj;
        }
        // If array is empty (handled by `value.length === 0` check if we refine it there)
        // or items are not ZWNode/ZWListItem (should not happen from valid parseZW)
        return {}; // Fallback to represent as an empty object
    }
    return null; // Should ideally not be reached for valid parsed ZW
};


export const convertZwToJsonObject = (zwString: string): object | null => {
  const parsedRootNode = parseZW(zwString);

  if (!parsedRootNode || parsedRootNode.key.startsWith('Error:')) {
    console.error('ZW to JSON Error: ZW Parsing failed.', parsedRootNode?.key, parsedRootNode?.value);
    return null;
  }

  const rootValue = parsedRootNode.value;

  if (rootValue === undefined) { // e.g. ZW-ROOT: (with no children defined under it)
    return {};
  }

  if (typeof rootValue === 'string') {
    // This means the ZW was like "ROOT_TYPE: some_string_value"
    // This isn't a structure that directly forms a JSON object from its *content*.
    console.warn('ZW to JSON Warning: The ZW root packet has a direct string value. This function expects the root packet to define a structure (object or list of objects). Returning null.');
    return null; 
  }

  if (Array.isArray(rootValue)) {
    // rootValue is an array of ZWNodess (forming an object) or ZWListItems (forming an array).
    const convertedValue = convertZwValueToJson(rootValue);

    if (typeof convertedValue === 'object' && convertedValue !== null && !Array.isArray(convertedValue)) {
      // This occurs if rootValue was an array of ZWNodess (e.g., ZW-DATA:\n KEY1: VAL1\n KEY2: VAL2)
      return convertedValue;
    } else if (Array.isArray(convertedValue)) {
      // This occurs if rootValue was an array of ZWListItems (e.g., ZW-LIST-DATA:\n - VAL1\n - NAME: VAL2)
      // The function is convertZwToJson*Object*. So, an array at the root content level isn't an object.
      console.warn("ZW to JSON Warning: The ZW root packet's content forms a list, not a direct JSON object. Wrapping it under 'root_items' key to fit 'object' return type.");
      return { "root_items": convertedValue };
    } else {
      // convertedValue is primitive or null, which means the ZW structure was not an object.
      console.error('ZW to JSON Error: Conversion of ZW root content did not result in a structured object or list.', convertedValue);
      return null;
    }
  }

  console.error("ZW to JSON Error: Unexpected structure for parsed ZW root node's value.", rootValue);
  return null;
};
