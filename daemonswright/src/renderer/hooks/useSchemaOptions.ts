/**
 * useSchemaOptions Hook
 * 
 * Loads field options from _schema.yaml files and allows adding new options.
 * Options are parsed from schema documentation format like:
 *   # Options: "option1", "option2", "option3"
 */

import { useState, useEffect, useCallback } from 'react';

interface SchemaOptions {
  [fieldName: string]: string[];
}

interface UseSchemaOptionsResult {
  roomOptions: SchemaOptions;
  areaOptions: SchemaOptions;
  isLoading: boolean;
  addOption: (schemaType: 'room' | 'area', fieldName: string, newOption: string) => Promise<boolean>;
}

// Parse options from schema comment line like: # Options: "option1", "option2", "option3"
function parseOptionsLine(line: string): string[] {
  const match = line.match(/Options:\s*(.+)/i);
  if (!match) return [];
  
  // Extract quoted strings
  const optionsStr = match[1];
  const options: string[] = [];
  const regex = /"([^"]+)"/g;
  let optionMatch;
  while ((optionMatch = regex.exec(optionsStr)) !== null) {
    options.push(optionMatch[1]);
  }
  return options;
}

// Parse schema file content to extract field options
function parseSchemaOptions(content: string): SchemaOptions {
  const options: SchemaOptions = {};
  const lines = content.split('\n');
  
  let currentField: string | null = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Check for field definition (starts with field name, no leading whitespace)
    const fieldMatch = line.match(/^(\w+):\s/);
    if (fieldMatch) {
      currentField = fieldMatch[1];
    }
    
    // Check for Options line (indented under field)
    if (currentField && line.includes('Options:')) {
      const fieldOptions = parseOptionsLine(line);
      if (fieldOptions.length > 0) {
        options[currentField] = fieldOptions;
      }
    }
  }
  
  return options;
}

// Add a new option to a schema file
function addOptionToSchema(content: string, fieldName: string, newOption: string): string {
  const lines = content.split('\n');
  let currentField: string | null = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Check for field definition
    const fieldMatch = line.match(/^(\w+):\s/);
    if (fieldMatch) {
      currentField = fieldMatch[1];
    }
    
    // Find Options line for the target field
    if (currentField === fieldName && line.includes('Options:')) {
      // Check if option already exists
      if (line.includes(`"${newOption}"`)) {
        return content; // Already exists
      }
      
      // Add new option before the last quote
      const lastQuoteIndex = line.lastIndexOf('"');
      if (lastQuoteIndex > 0) {
        const newLine = line.slice(0, lastQuoteIndex + 1) + `, "${newOption}"` + line.slice(lastQuoteIndex + 1);
        lines[i] = newLine;
        return lines.join('\n');
      }
    }
  }
  
  return content; // No change if field not found
}

export function useSchemaOptions(worldDataPath: string | null): UseSchemaOptionsResult {
  const [roomOptions, setRoomOptions] = useState<SchemaOptions>({});
  const [areaOptions, setAreaOptions] = useState<SchemaOptions>({});
  const [isLoading, setIsLoading] = useState(false);

  // Load schema files
  useEffect(() => {
    if (!worldDataPath) return;

    const loadSchemas = async () => {
      setIsLoading(true);
      try {
        // Load room schema
        const roomSchemaPath = `${worldDataPath}/rooms/_schema.yaml`;
        try {
          const roomContent = await window.daemonswright.fs.readFile(roomSchemaPath);
          setRoomOptions(parseSchemaOptions(roomContent));
        } catch (err) {
          console.warn('Could not load room schema:', err);
        }

        // Load area schema
        const areaSchemaPath = `${worldDataPath}/areas/_schema.yaml`;
        try {
          const areaContent = await window.daemonswright.fs.readFile(areaSchemaPath);
          setAreaOptions(parseSchemaOptions(areaContent));
        } catch (err) {
          console.warn('Could not load area schema:', err);
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadSchemas();
  }, [worldDataPath]);

  // Add a new option to a schema field
  const addOption = useCallback(async (
    schemaType: 'room' | 'area',
    fieldName: string,
    newOption: string
  ): Promise<boolean> => {
    if (!worldDataPath) return false;

    try {
      const schemaPath = schemaType === 'room'
        ? `${worldDataPath}/rooms/_schema.yaml`
        : `${worldDataPath}/areas/_schema.yaml`;

      // Read current content
      const content = await window.daemonswright.fs.readFile(schemaPath);
      
      // Add new option
      const updatedContent = addOptionToSchema(content, fieldName, newOption);
      
      // Write back if changed
      if (updatedContent !== content) {
        await window.daemonswright.fs.writeFile(schemaPath, updatedContent);
        
        // Update local state
        if (schemaType === 'room') {
          setRoomOptions(parseSchemaOptions(updatedContent));
        } else {
          setAreaOptions(parseSchemaOptions(updatedContent));
        }
      }
      
      return true;
    } catch (err) {
      console.error('Failed to add option to schema:', err);
      return false;
    }
  }, [worldDataPath]);

  return {
    roomOptions,
    areaOptions,
    isLoading,
    addOption,
  };
}
