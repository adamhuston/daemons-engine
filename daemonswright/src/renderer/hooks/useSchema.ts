/**
 * useSchema Hook
 *
 * Manages schema loading and content validation:
 * - Load schemas from world_data/_schema.yaml files
 * - Validate content against schemas
 * - Track validation errors
 */

import { useState, useCallback, useEffect } from 'react';
import type { SchemaDefinition, ValidationError } from '../../shared/types';

interface SchemaState {
  schemas: Record<string, SchemaDefinition>;
  validationErrors: ValidationError[];
  isLoading: boolean;
}

export function useSchema(worldDataPath: string | null) {
  const [state, setState] = useState<SchemaState>({
    schemas: {},
    validationErrors: [],
    isLoading: false,
  });

  // Load schemas when world data path changes
  useEffect(() => {
    if (worldDataPath) {
      loadSchemas(worldDataPath);
    }
  }, [worldDataPath]);

  // Load all schemas from world_data directory
  const loadSchemas = useCallback(async (path: string) => {
    setState((prev) => ({ ...prev, isLoading: true }));

    try {
      const schemas = await window.daemonswright.schema.loadSchemas(path);
      setState((prev) => ({
        ...prev,
        schemas,
        isLoading: false,
      }));
    } catch (error) {
      console.error('Failed to load schemas:', error);
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  // Validate content against schema
  const validateContent = useCallback(async (content: string, filePath: string) => {
    // Infer content type from file path
    const pathParts = filePath.split(/[/\\]/);
    const contentType = pathParts.find((part) =>
      ['rooms', 'items', 'npcs', 'quests', 'abilities', 'classes', 'areas', 'dialogues', 'triggers', 'factions', 'npc_spawns', 'item_instances', 'quest_chains'].includes(part)
    );

    if (!contentType) {
      // Can't determine content type, skip validation
      return;
    }

    try {
      const result = await window.daemonswright.schema.validateContent(content, contentType);
      setState((prev) => ({
        ...prev,
        validationErrors: result.errors,
      }));
    } catch (error) {
      console.error('Validation error:', error);
    }
  }, []);

  // Get schema for a specific content type
  const getSchema = useCallback((contentType: string): SchemaDefinition | null => {
    return state.schemas[contentType] ?? null;
  }, [state.schemas]);

  // Clear validation errors
  const clearErrors = useCallback(() => {
    setState((prev) => ({
      ...prev,
      validationErrors: [],
    }));
  }, []);

  return {
    schemas: state.schemas,
    validationErrors: state.validationErrors,
    isLoading: state.isLoading,
    loadSchemas,
    validateContent,
    getSchema,
    clearErrors,
  };
}
