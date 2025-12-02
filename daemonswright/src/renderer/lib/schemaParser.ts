/**
 * Schema Parser
 *
 * Parses _schema.yaml files and generates TypeScript/Zod definitions.
 */

import yaml from 'js-yaml';
import { z, ZodSchema } from 'zod';
import type { SchemaDefinition, SchemaField } from '../../shared/types';

/**
 * Parse a _schema.yaml file content into a SchemaDefinition
 */
export function parseSchema(content: string): SchemaDefinition {
  const raw = yaml.load(content) as Record<string, unknown>;

  return {
    name: String(raw.name ?? 'Unknown'),
    description: raw.description ? String(raw.description) : undefined,
    fields: parseFields(raw.fields as Record<string, unknown> ?? {}),
    examples: Array.isArray(raw.examples) ? raw.examples : undefined,
  };
}

/**
 * Parse field definitions from schema
 */
function parseFields(fields: Record<string, unknown>): Record<string, SchemaField> {
  const result: Record<string, SchemaField> = {};

  for (const [name, def] of Object.entries(fields)) {
    const fieldDef = def as Record<string, unknown>;
    result[name] = {
      type: String(fieldDef.type ?? 'string'),
      description: fieldDef.description ? String(fieldDef.description) : undefined,
      required: Boolean(fieldDef.required ?? false),
      default: fieldDef.default,
      enum: Array.isArray(fieldDef.enum) ? fieldDef.enum.map(String) : undefined,
      ref: fieldDef.ref ? String(fieldDef.ref) : undefined,
    };
  }

  return result;
}

/**
 * Generate a Zod schema from a SchemaDefinition
 */
export function generateZodSchema(schema: SchemaDefinition): ZodSchema {
  const shape: Record<string, ZodSchema> = {};

  for (const [name, field] of Object.entries(schema.fields)) {
    let fieldSchema = createFieldSchema(field);

    if (!field.required) {
      fieldSchema = fieldSchema.optional();
    }

    shape[name] = fieldSchema;
  }

  return z.object(shape);
}

/**
 * Create a Zod schema for a single field
 */
function createFieldSchema(field: SchemaField): ZodSchema {
  switch (field.type) {
    case 'string':
      if (field.enum) {
        return z.enum(field.enum as [string, ...string[]]);
      }
      return z.string();

    case 'number':
    case 'integer':
      return z.number();

    case 'boolean':
      return z.boolean();

    case 'array':
      return z.array(z.unknown());

    case 'object':
      return z.record(z.unknown());

    default:
      return z.unknown();
  }
}

/**
 * Validate content against a Zod schema
 */
export function validateWithZod(content: unknown, schema: ZodSchema): { valid: boolean; errors: Array<{ path: string; message: string }> } {
  const result = schema.safeParse(content);

  if (result.success) {
    return { valid: true, errors: [] };
  }

  const errors = result.error.issues.map((issue) => ({
    path: issue.path.join('.'),
    message: issue.message,
  }));

  return { valid: false, errors };
}
