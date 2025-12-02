/**
 * YAML Utilities
 *
 * Helper functions for working with YAML content.
 */

import yaml from 'js-yaml';

/**
 * Parse YAML content safely
 */
export function parseYaml<T = unknown>(content: string): { data: T | null; error: string | null } {
  try {
    const data = yaml.load(content) as T;
    return { data, error: null };
  } catch (error) {
    const yamlError = error as yaml.YAMLException;
    return {
      data: null,
      error: yamlError.message,
    };
  }
}

/**
 * Serialize data to YAML
 */
export function toYaml(data: unknown): string {
  return yaml.dump(data, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
  });
}

/**
 * Get line number from YAML parse error
 */
export function getErrorLine(error: yaml.YAMLException): number {
  return error.mark?.line ?? 0;
}

/**
 * Get column number from YAML parse error
 */
export function getErrorColumn(error: yaml.YAMLException): number {
  return error.mark?.column ?? 0;
}

/**
 * Extract all keys from a YAML document
 */
export function extractKeys(content: string): string[] {
  const { data } = parseYaml<Record<string, unknown>>(content);
  if (!data || typeof data !== 'object') {
    return [];
  }
  return Object.keys(data);
}

/**
 * Find all references to other content in a YAML document
 */
export function findReferences(content: string, refFields: string[]): Array<{ field: string; value: string }> {
  const { data } = parseYaml<Record<string, unknown>>(content);
  if (!data || typeof data !== 'object') {
    return [];
  }

  const refs: Array<{ field: string; value: string }> = [];

  function traverse(obj: unknown, path: string = '') {
    if (!obj || typeof obj !== 'object') return;

    for (const [key, value] of Object.entries(obj)) {
      const currentPath = path ? `${path}.${key}` : key;

      if (refFields.includes(key) && typeof value === 'string') {
        refs.push({ field: currentPath, value });
      }

      if (typeof value === 'object') {
        traverse(value, currentPath);
      }
    }
  }

  traverse(data);
  return refs;
}
