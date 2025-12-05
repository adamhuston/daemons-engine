/**
 * Schema IPC Handlers
 *
 * Handles schema loading and validation from _schema.yaml files:
 * - Load all schemas from world_data directory
 * - Parse schema definitions
 * - Validate content against schemas
 */

import { ipcMain } from 'electron';
import fs from 'fs/promises';
import path from 'path';
import yaml from 'js-yaml';
import type { SchemaDefinition } from '../../shared/types';

// Cache loaded schemas
const schemaCache = new Map<string, SchemaDefinition>();

/**
 * Parse a schema file that may be in doc-style format (field: type) or structured format.
 * Doc-style example:
 *   id: string
 *   name: string
 *   count: int (default: 0)
 */
function parseSchemaFile(content: string, contentType: string): SchemaDefinition {
  // Try structured format first (proper YAML with a 'fields' key)
  try {
    const parsed = yaml.load(content) as Record<string, unknown> | null;
    if (parsed && typeof parsed === 'object' && 'fields' in parsed) {
      return parsed as unknown as SchemaDefinition;
    }
  } catch {
    // YAML parse failed, fall through to line-by-line parsing
  }

  // Parse doc-style format: "fieldName: type (default: x)" with optional comments
  // This handles schema files that are documentation-style, not strict YAML
  const fields: Record<string, { type: string; required?: boolean; default?: unknown; enum?: string[] }> = {};
  const lines = content.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Skip comments, empty lines, and indented lines (which are descriptions)
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('//')) continue;
    // Skip lines that start with whitespace (descriptions under fields)
    if (line.startsWith(' ') || line.startsWith('\t')) continue;

    // Match pattern: fieldName: type (optional stuff)
    // Examples: "id: string", "count: int (default: 0)", "biome: string (default: \"ethereal\")"
    const match = trimmed.match(/^(\w+):\s*(\w+)(?:\s*\(.*?\))?/);
    if (match) {
      const [, fieldName, fieldType] = match;
      // Normalize types
      const normalizedType =
        fieldType === 'int' ? 'integer' :
        fieldType === 'float' ? 'number' :
        fieldType === 'bool' ? 'boolean' :
        fieldType;

      // Check for default in parens
      const defaultMatch = trimmed.match(/\(default:\s*(.+?)\)/);
      const hasDefault = !!defaultMatch;

      // Look ahead for # Options: comment in the next few lines
      let enumValues: string[] | undefined;
      for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
        const nextLine = lines[j].trim();
        // Stop if we hit a new field definition
        if (nextLine.match(/^\w+:\s*\w+/)) break;
        // Look for Options: comment
        const optionsMatch = nextLine.match(/^#\s*Options?:\s*(.+)/i);
        if (optionsMatch) {
          // Parse options like: "ethereal", "forest", "cave" or ethereal, forest, cave
          const optionsStr = optionsMatch[1];
          enumValues = optionsStr
            .split(',')
            .map(s => s.trim().replace(/^["']|["']$/g, ''))
            .filter(s => s.length > 0);
          break;
        }
      }

      fields[fieldName] = {
        type: normalizedType,
        required: !hasDefault,
        ...(enumValues && { enum: enumValues }),
      };
    }
  }

  return {
    name: contentType,
    fields,
  };
}

export function registerSchemaHandlers(): void {
  // Load all schemas from world_data directory
  ipcMain.handle('schema:loadSchemas', async (_event, worldDataPath: string) => {
    schemaCache.clear();
    console.log('[schema] Loading schemas from:', worldDataPath);

    try {
      const entries = await fs.readdir(worldDataPath, { withFileTypes: true });
      const schemas: Record<string, SchemaDefinition> = {};

      for (const entry of entries) {
        if (entry.isDirectory()) {
          const schemaPath = path.join(worldDataPath, entry.name, '_schema.yaml');
          try {
            const content = await fs.readFile(schemaPath, 'utf-8');
            // Parse the schema file - handles both structured and doc-style formats
            const schema = parseSchemaFile(content, entry.name);
            schemas[entry.name] = schema;
            schemaCache.set(entry.name, schema);
            console.log(`[schema] Loaded schema for: ${entry.name}`, Object.keys(schema.fields || {}));
          } catch (err) {
            // Directory doesn't have a schema file, skip it
            console.log(`[schema] No schema in ${entry.name}:`, (err as Error).message?.slice(0, 50));
          }
        }
      }

      console.log('[schema] Total schemas loaded:', schemaCache.size);
      return schemas;
    } catch (error) {
      throw new Error(`Failed to load schemas: ${error}`);
    }
  });

  // Validate content against a schema
  ipcMain.handle('schema:validateContent', async (_event, content: string, contentType: string) => {
    console.log('[schema] Validating content type:', contentType, 'cache size:', schemaCache.size);
    const schema = schemaCache.get(contentType);
    if (!schema) {
      return {
        valid: false,
        errors: [{ message: `No schema found for content type: ${contentType}` }],
      };
    }

    try {
      // Parse YAML first
      const parsed = yaml.load(content) as Record<string, unknown> | null;

      // If parsing succeeded but content is empty or null, just return valid
      if (!parsed || typeof parsed !== 'object') {
        return { valid: true, errors: [] };
      }

      // Helper to find line number of a field in the raw content
      const lines = content.split('\n');
      const findFieldLine = (fieldName: string): number => {
        // Look for "fieldName:" at the start of a line (top-level field)
        const regex = new RegExp(`^${fieldName}\\s*:`);
        for (let i = 0; i < lines.length; i++) {
          if (regex.test(lines[i])) {
            return i + 1; // 1-indexed
          }
        }
        return 1; // Default to line 1 if not found
      };

      const errors: { line?: number; column?: number; message: string }[] = [];

      // Validate each field defined in schema
      for (const [fieldName, fieldDef] of Object.entries(schema.fields ?? {})) {
        const value = parsed[fieldName];

        // Check required
        if (fieldDef.required && value === undefined) {
          errors.push({ line: 1, column: 1, message: `Missing required field: ${fieldName}` });
          continue;
        }

        if (value === undefined) continue;

        const fieldLine = findFieldLine(fieldName);

        // Check type
        const expectedType = fieldDef.type;
        let actualType: string = typeof value;
        if (Array.isArray(value)) actualType = 'array';
        if (value === null) actualType = 'null';

        const typeMatch =
          expectedType === 'string' ? actualType === 'string' :
          expectedType === 'integer' || expectedType === 'int' ? actualType === 'number' && Number.isInteger(value) :
          expectedType === 'number' || expectedType === 'float' ? actualType === 'number' :
          expectedType === 'boolean' || expectedType === 'bool' ? actualType === 'boolean' :
          expectedType === 'array' || expectedType === 'list' ? actualType === 'array' :
          expectedType === 'object' || expectedType === 'dict' || expectedType === 'map' ? actualType === 'object' && !Array.isArray(value) :
          true; // unknown type, skip

        if (!typeMatch) {
          errors.push({ line: fieldLine, column: 1, message: `Field '${fieldName}' should be ${expectedType}, got ${actualType}` });
        }

        // Check enum
        if (fieldDef.enum && !fieldDef.enum.includes(value as string)) {
          errors.push({ line: fieldLine, column: 1, message: `Field '${fieldName}' must be one of: ${fieldDef.enum.join(', ')}` });
        }
      }

      return { valid: errors.length === 0, errors };
    } catch (error) {
      const yamlError = error as yaml.YAMLException;
      return {
        valid: false,
        errors: [
          {
            line: (yamlError.mark?.line ?? 0) + 1,
            column: (yamlError.mark?.column ?? 0) + 1,
            message: yamlError.message,
          },
        ],
      };
    }
  });

  // Get schema for a specific content type
  ipcMain.handle('schema:getSchemaForType', async (_event, contentType: string) => {
    return schemaCache.get(contentType) ?? null;
  });
}
