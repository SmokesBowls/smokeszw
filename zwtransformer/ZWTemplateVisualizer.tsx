
import React from 'react';
import { ZWNode, ZWListItem, parseZW } from './zwParser'; // Updated import

// ZWNode, ZWListItem interfaces, getIndentation, and parseZWForVisualizer are removed.
// They will now reside in zwParser.ts.

const renderValue = (
  val: ZWNode['value'] | ZWListItem['value'], 
  depth: number
): JSX.Element | null => {
  if (typeof val === 'string') {
    return val.trim() === '' ? null : <span style={{ color: '#27ae60', whiteSpace: 'pre-wrap' }}>{val}</span>;
  }
  if (val === undefined || val === null) {
    return null;
  }
  if (Array.isArray(val) && val.length > 0) {
    const childrenToRender = val.filter(child => child !== undefined && child !== null);
    if (childrenToRender.length === 0) return null;

    return (
      <ul style={{ listStyleType: 'none', paddingLeft: `10px`, margin: '2px 0' }}>
        {childrenToRender.map((child, index) => (
          <li key={index}>
            <RenderNode node={child as ZWNode | ZWListItem} /> 
          </li>
        ))}
      </ul>
    );
  }
  return null;
};

const RenderNode: React.FC<{ node: ZWNode | ZWListItem }> = ({ node }) => {
  if ('key' in node && node.key !== undefined) {
    const zwNode = node as ZWNode;
    const valueOutput = renderValue(zwNode.value, zwNode.depth);

    return (
      <div style={{ marginLeft: `${zwNode.depth * 10 - (zwNode.depth > 0 ? 10:0) }px`}}>
        <strong style={{ color: zwNode.depth === 0 ? '#5D3FD3' : '#c0392b', fontSize: zwNode.depth === 0 ? '1.1em': '1em' }}>
          {zwNode.key}:
        </strong>
        {(typeof zwNode.value === 'string' && zwNode.value.trim() !== '' && valueOutput) ? ' ' : ''}
        {valueOutput}
      </div>
    );
  } else { 
    const listItem = node as ZWListItem;
    const valueElement = renderValue(listItem.value, listItem.depth); 
    
    // Use listItem.delimiter in rendering if needed, though current style uses ':' visually for keys
    const displayDelimiter = listItem.isKeyValue ? ':' : '';


    if (listItem.isKeyValue && listItem.itemKey) {
      return (
        <div style={{ marginLeft: `${listItem.depth * 10 -10 }px`}}>
          <span style={{ fontWeight: 'normal', color: '#2980b9' }}>- </span>
          <strong style={{ color: '#c0392b' }}>{listItem.itemKey}{displayDelimiter}</strong>
          {(valueElement && typeof listItem.value === 'string' && listItem.value.trim() !== '') ? ' ' : ''}
          {valueElement}
        </div>
      );
    }
    return (
      <div style={{ marginLeft: `${listItem.depth * 10 -10 }px`}}>
        <span style={{ fontWeight: 'normal', color: '#2980b9' }}>- </span>
        {valueElement}
      </div>
    );
  }
};


const ZWTemplateVisualizer: React.FC<{ templateDefinition: string }> = ({ templateDefinition }) => {
  // Use the new shared parser.
  // For visualization, we typically use the default ':' delimiter.
  // If a future feature allows specifying delimiter for visualization, it can be passed here.
  const parsedStructure = parseZW(templateDefinition); 

  if (!parsedStructure) {
    return <p style={{color: '#7f8c8d'}}>Type ZW code to see visual preview...</p>;
  }
  
  if (parsedStructure.key.startsWith('Error:')) {
     return <p style={{color: 'red', whiteSpace: 'pre-wrap'}}>{parsedStructure.key} {typeof parsedStructure.value === 'string' ? parsedStructure.value : ''}</p>;
  }

  return (
    <div className="zw-visualizer-tree" style={{ fontFamily: "'Courier New', Courier, monospace", fontSize: '0.85em', lineHeight: '1.6' }}>
      <RenderNode node={parsedStructure} />
    </div>
  );
};

export default ZWTemplateVisualizer;
