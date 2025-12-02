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

export function registerSchemaHandlers(): void {
  // Load all schemas from world_data directory
  ipcMain.handle('schema:loadSchemas', async (_event, worldDataPath: string) => {
    schemaCache.clear();

    try {
      const entries = await fs.readdir(worldDataPath, { withFileTypes: true });
      const schemas: Record<string, SchemaDefinition> = {};

      for (const entry of entries) {
        if (entry.isDirectory()) {
          const schemaPath = path.join(worldDataPath, entry.name, '_schema.yaml');
          try {
            const content = await fs.readFile(schemaPath, 'utf-8');
            const schema = yaml.load(content) as SchemaDefinition;
            schemas[entry.name] = schema;
            schemaCache.set(entry.name, schema);
          } catch {
            // Directory doesn't have a schema file, skip it
          }
        }
      }

      return schemas;
    } catch (error) {
      throw new Error(`Failed to load schemas: ${error}`);
    }
  });

  // Validate content against a schema
  ipcMain.handle('schema:validateContent', async (_event, content: string, contentType: string) => {
    const schema = schemaCache.get(contentType);
    if (!schema) {
      return {
        valid: false,
        errors: [{ message: `No schema found for content type: ${contentType}` }],
      };
    }

    try {
      // Parse YAML first
      yaml.load(content);

      // TODO: Implement full schema validation using Zod
      // For now, just check YAML syntax
      return { valid: true, errors: [] };
    } catch (error) {
      const yamlError = error as yaml.YAMLException;
      return {
        valid: false,
        errors: [
          {
            line: yamlError.mark?.line ?? 0,
            column: yamlError.mark?.column ?? 0,
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
