/**
 * useQuests Hook
 * 
 * Manages quest data for the Quest Designer.
 * Handles loading from and saving to YAML files.
 */
import { useState, useEffect, useCallback } from 'react';
import yaml from 'js-yaml';
import type { FileEntry } from '../../shared/types';

// ============================================================================
// Types
// ============================================================================

export interface QuestObjective {
  id: string;
  type: 'kill' | 'collect' | 'visit' | 'talk' | 'deliver' | 'interact' | 'escort' | 'survive';
  description: string;
  target_template_id?: string;
  target_room_id?: string;
  item_template_id?: string;
  npc_template_id?: string;
  required_count?: number;
  hidden?: boolean;
  optional?: boolean;
}

export interface QuestReward {
  experience?: number;
  gold?: number;
  items?: Array<{ template_id: string; quantity: number }>;
  abilities?: string[];
  flags?: Record<string, unknown>;
}

export interface Quest {
  // Core identification
  id: string;
  name: string;
  description: string;
  category: 'main' | 'side' | 'daily' | 'repeatable' | 'epic';
  
  // NPCs
  giver_npc_template?: string;
  turn_in_npc_template?: string;
  
  // Requirements
  level_requirement?: number;
  prerequisites?: string[];
  required_flags?: Record<string, unknown>;
  required_items?: string[];
  required_class?: string;
  
  // Objectives and rewards
  objectives: QuestObjective[];
  rewards?: QuestReward;
  
  // Editor metadata
  filePath?: string;
  position?: { x: number; y: number };
}

interface UseQuestsOptions {
  worldDataPath: string | null;
  enabled?: boolean;
}

export interface UseQuestsResult {
  quests: Quest[];
  loading: boolean;
  error: string | null;
  
  // CRUD operations
  createQuest: (quest: Partial<Quest>) => Promise<boolean>;
  updateQuest: (questId: string, updates: Partial<Quest>) => Promise<boolean>;
  deleteQuest: (questId: string) => Promise<boolean>;
  updateQuestPosition: (questId: string, position: { x: number; y: number }) => void;
  
  // Prerequisite operations
  addPrerequisite: (questId: string, prerequisiteId: string) => Promise<boolean>;
  removePrerequisite: (questId: string, prerequisiteId: string) => Promise<boolean>;
  
  // Reload
  reload: () => Promise<void>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Parse quest YAML file content
 */
function parseQuestFile(content: string, filePath: string): Quest | null {
  try {
    const data = yaml.load(content) as Record<string, unknown>;
    if (!data || typeof data !== 'object' || !data.id) {
      return null;
    }
    
    return {
      id: data.id as string,
      name: (data.name as string) || data.id as string,
      description: (data.description as string) || '',
      category: (data.category as Quest['category']) || 'side',
      giver_npc_template: data.giver_npc_template as string | undefined,
      turn_in_npc_template: data.turn_in_npc_template as string | undefined,
      level_requirement: data.level_requirement as number | undefined,
      prerequisites: (data.prerequisites as string[]) || [],
      required_flags: data.required_flags as Record<string, unknown> | undefined,
      required_items: data.required_items as string[] | undefined,
      required_class: data.required_class as string | undefined,
      objectives: (data.objectives as QuestObjective[]) || [],
      rewards: data.rewards as QuestReward | undefined,
      filePath,
      // Default position based on quest index (will be overridden by layout)
      position: { x: 0, y: 0 },
    };
  } catch (err) {
    console.error(`Failed to parse quest file ${filePath}:`, err);
    return null;
  }
}

/**
 * Serialize quest back to YAML format
 */
function serializeQuest(quest: Quest): string {
  // Remove editor-only fields
  const { filePath, position, ...questData } = quest;
  
  return yaml.dump(questData, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useQuests(options: UseQuestsOptions): UseQuestsResult {
  const { worldDataPath, enabled = true } = options;
  
  const [quests, setQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Load Quests
  // -------------------------------------------------------------------------
  const loadQuests = useCallback(async () => {
    if (!worldDataPath) {
      console.log('[useQuests] No worldDataPath, skipping load');
      return;
    }
    
    console.log('[useQuests] Loading quests from:', worldDataPath);
    
    try {
      const questsPath = `${worldDataPath}/quests`;
      console.log('[useQuests] Looking in:', questsPath);
      
      // Recursively find all YAML files in quests directory and subdirectories
      const findYamlFiles = async (dirPath: string): Promise<FileEntry[]> => {
        const entries = await window.daemonswright.fs.listDirectory(dirPath);
        const yamlFiles: FileEntry[] = [];
        
        for (const entry of entries) {
          if (entry.isDirectory && !entry.name.startsWith('_')) {
            // Recurse into subdirectories
            const subFiles = await findYamlFiles(entry.path);
            yamlFiles.push(...subFiles);
          } else if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
            yamlFiles.push(entry);
          }
        }
        
        return yamlFiles;
      };
      
      const yamlFiles = await findYamlFiles(questsPath);
      console.log('[useQuests] YAML files found:', yamlFiles.length, yamlFiles.map((f: FileEntry) => f.name));
      
      const loadedQuests: Quest[] = [];
      let xPos = 100;
      
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const quest = parseQuestFile(content, entry.path);
          if (quest) {
            // Simple auto-layout for now
            quest.position = { x: xPos, y: 100 };
            xPos += 250;
            loadedQuests.push(quest);
          }
        } catch (err) {
          console.warn(`Failed to load quest file ${entry.name}:`, err);
        }
      }
      
      // Try to load positions from layout file
      try {
        const layoutPath = `${questsPath}/_layout.yaml`;
        const layoutExists = await window.daemonswright.fs.fileExists(layoutPath);
        if (layoutExists) {
          const layoutContent = await window.daemonswright.fs.readFile(layoutPath);
          const layout = yaml.load(layoutContent) as Record<string, { x: number; y: number }>;
          
          if (layout && typeof layout === 'object') {
            for (const quest of loadedQuests) {
              if (layout[quest.id]) {
                quest.position = layout[quest.id];
              }
            }
          }
        }
      } catch {
        // Layout file doesn't exist, use auto-layout
      }
      
      setQuests(loadedQuests);
    } catch (err) {
      console.warn('Failed to load quests:', err);
      setQuests([]);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Save Layout
  // -------------------------------------------------------------------------
  const saveLayout = useCallback(async () => {
    if (!worldDataPath) return;
    
    const layout: Record<string, { x: number; y: number }> = {};
    for (const quest of quests) {
      if (quest.position) {
        layout[quest.id] = quest.position;
      }
    }
    
    const content = yaml.dump(layout, {
      indent: 2,
      lineWidth: -1,
    });
    
    await window.daemonswright.fs.writeFile(`${worldDataPath}/quests/_layout.yaml`, content);
  }, [worldDataPath, quests]);

  // -------------------------------------------------------------------------
  // Main Load Function
  // -------------------------------------------------------------------------
  const reload = useCallback(async () => {
    if (!worldDataPath) return;
    
    setLoading(true);
    setError(null);
    
    try {
      await loadQuests();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load quests';
      setError(message);
      console.error('Failed to load quests:', err);
    } finally {
      setLoading(false);
    }
  }, [worldDataPath, loadQuests]);

  // Load on mount when enabled
  useEffect(() => {
    if (enabled) {
      reload();
    }
  }, [reload, enabled]);

  // -------------------------------------------------------------------------
  // CRUD Operations
  // -------------------------------------------------------------------------
  const createQuest = useCallback(async (questData: Partial<Quest>): Promise<boolean> => {
    if (!worldDataPath || !questData.id) return false;
    
    const newQuest: Quest = {
      id: questData.id,
      name: questData.name || questData.id,
      description: questData.description || '',
      category: questData.category || 'side',
      objectives: questData.objectives || [],
      prerequisites: questData.prerequisites || [],
      position: questData.position || { x: 100 + quests.length * 250, y: 100 },
      ...questData,
    };
    
    const filePath = `${worldDataPath}/quests/${newQuest.id}.yaml`;
    newQuest.filePath = filePath;
    
    try {
      const content = serializeQuest(newQuest);
      await window.daemonswright.fs.writeFile(filePath, content);
      
      setQuests(prev => [...prev, newQuest]);
      await saveLayout();
      return true;
    } catch (err) {
      console.error('Failed to create quest:', err);
      return false;
    }
  }, [worldDataPath, quests, saveLayout]);

  const updateQuest = useCallback(async (questId: string, updates: Partial<Quest>): Promise<boolean> => {
    const quest = quests.find(q => q.id === questId);
    if (!quest || !quest.filePath) return false;
    
    const updatedQuest = { ...quest, ...updates };
    
    try {
      const content = serializeQuest(updatedQuest);
      await window.daemonswright.fs.writeFile(quest.filePath, content);
      
      setQuests(prev => prev.map(q => q.id === questId ? updatedQuest : q));
      return true;
    } catch (err) {
      console.error('Failed to update quest:', err);
      return false;
    }
  }, [quests]);

  const deleteQuest = useCallback(async (questId: string): Promise<boolean> => {
    const quest = quests.find(q => q.id === questId);
    if (!quest || !quest.filePath) return false;
    
    try {
      await window.daemonswright.fs.deleteFile(quest.filePath);
      setQuests(prev => prev.filter(q => q.id !== questId));
      await saveLayout();
      return true;
    } catch (err) {
      console.error('Failed to delete quest:', err);
      return false;
    }
  }, [quests, saveLayout]);

  const updateQuestPosition = useCallback((questId: string, position: { x: number; y: number }) => {
    setQuests(prev => prev.map(q => q.id === questId ? { ...q, position } : q));
    // Debounce layout save
    setTimeout(() => saveLayout(), 500);
  }, [saveLayout]);

  // -------------------------------------------------------------------------
  // Prerequisite Operations
  // -------------------------------------------------------------------------
  const addPrerequisite = useCallback(async (questId: string, prerequisiteId: string): Promise<boolean> => {
    const quest = quests.find(q => q.id === questId);
    if (!quest) return false;
    
    if (quest.prerequisites?.includes(prerequisiteId)) return true; // Already exists
    
    const newPrereqs = [...(quest.prerequisites || []), prerequisiteId];
    return updateQuest(questId, { prerequisites: newPrereqs });
  }, [quests, updateQuest]);

  const removePrerequisite = useCallback(async (questId: string, prerequisiteId: string): Promise<boolean> => {
    const quest = quests.find(q => q.id === questId);
    if (!quest) return false;
    
    const newPrereqs = (quest.prerequisites || []).filter(p => p !== prerequisiteId);
    return updateQuest(questId, { prerequisites: newPrereqs });
  }, [quests, updateQuest]);

  // -------------------------------------------------------------------------
  // Return Hook Result
  // -------------------------------------------------------------------------
  return {
    quests,
    loading,
    error,
    
    createQuest,
    updateQuest,
    deleteQuest,
    updateQuestPosition,
    
    addPrerequisite,
    removePrerequisite,
    
    reload,
  };
}
