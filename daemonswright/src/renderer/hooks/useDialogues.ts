/**
 * useDialogues Hook
 * 
 * Manages dialogue tree data for the Dialogue Editor.
 * Handles loading from and saving to YAML files.
 */
import { useState, useEffect, useCallback } from 'react';
import yaml from 'js-yaml';
import type { FileEntry } from '../../shared/types';

// ============================================================================
// Types
// ============================================================================

export interface DialogueOption {
  text: string;
  next_node: string | null;
  accept_quest?: string;
  turn_in_quest?: string;
  conditions?: Array<{ type: string; params?: Record<string, unknown> }>;
  set_flags?: Record<string, unknown>;
  give_items?: Array<[string, number]>;
  remove_items?: Array<[string, number]>;
  grant_experience?: number;
}

export interface DialogueNode {
  id: string;
  text: string;
  options: DialogueOption[];
  // Editor metadata
  position?: { x: number; y: number };
}

export interface EntryOverride {
  conditions: Array<{ type: string; params?: Record<string, unknown> }>;
  node_id: string;
}

export interface DialogueTree {
  npc_template_id: string;
  entry_node: string;
  entry_overrides?: EntryOverride[];
  nodes: Record<string, Omit<DialogueNode, 'id'>>;
  // Editor metadata
  filePath?: string;
  layout?: Record<string, { x: number; y: number }>;
}

interface UseDialoguesOptions {
  worldDataPath: string | null;
  enabled?: boolean;
}

export interface UseDialoguesResult {
  dialogueTrees: DialogueTree[];
  selectedTree: DialogueTree | null;
  loading: boolean;
  error: string | null;
  
  // Selection
  selectTree: (npcTemplateId: string | null) => void;
  
  // CRUD operations
  createDialogueTree: (tree: Partial<DialogueTree>) => Promise<boolean>;
  updateDialogueTree: (npcTemplateId: string, updates: Partial<DialogueTree>) => Promise<boolean>;
  deleteDialogueTree: (npcTemplateId: string) => Promise<boolean>;
  
  // Node operations
  addNode: (nodeId: string, node: Omit<DialogueNode, 'id'>) => Promise<boolean>;
  updateNode: (nodeId: string, updates: Partial<DialogueNode>) => Promise<boolean>;
  deleteNode: (nodeId: string) => Promise<boolean>;
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  
  // Connection operations
  addConnection: (sourceNodeId: string, optionIndex: number, targetNodeId: string) => Promise<boolean>;
  removeConnection: (sourceNodeId: string, optionIndex: number) => Promise<boolean>;
  
  // Reload
  reload: () => Promise<void>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Parse dialogue YAML file content
 */
function parseDialogueFile(content: string, filePath: string): DialogueTree | null {
  try {
    const data = yaml.load(content) as Record<string, unknown>;
    if (!data || typeof data !== 'object' || !data.npc_template_id) {
      return null;
    }
    
    return {
      npc_template_id: data.npc_template_id as string,
      entry_node: (data.entry_node as string) || 'greet',
      entry_overrides: data.entry_overrides as EntryOverride[] | undefined,
      nodes: (data.nodes as Record<string, Omit<DialogueNode, 'id'>>) || {},
      filePath,
    };
  } catch (err) {
    console.error(`Failed to parse dialogue file ${filePath}:`, err);
    return null;
  }
}

/**
 * Serialize dialogue tree back to YAML format
 */
function serializeDialogue(tree: DialogueTree): string {
  // Remove editor-only fields
  const { filePath, layout, ...treeData } = tree;
  
  return yaml.dump(treeData, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
  });
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useDialogues(options: UseDialoguesOptions): UseDialoguesResult {
  const { worldDataPath, enabled = true } = options;
  
  const [dialogueTrees, setDialogueTrees] = useState<DialogueTree[]>([]);
  const [selectedTreeId, setSelectedTreeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get selected tree
  const selectedTree = dialogueTrees.find(t => t.npc_template_id === selectedTreeId) || null;

  // -------------------------------------------------------------------------
  // Load Dialogues
  // -------------------------------------------------------------------------
  const loadDialogues = useCallback(async () => {
    if (!worldDataPath) return;
    
    try {
      const dialoguesPath = `${worldDataPath}/dialogues`;
      
      // Recursively find all YAML files in dialogues directory and subdirectories
      const findYamlFiles = async (dirPath: string): Promise<FileEntry[]> => {
        const entries = await window.daemonswright.fs.listDirectory(dirPath);
        const yamlFiles: FileEntry[] = [];
        
        for (const entry of entries) {
          if (entry.isDirectory && !entry.name.startsWith('_')) {
            // Recurse into subdirectories
            const subFiles = await findYamlFiles(entry.path);
            yamlFiles.push(...subFiles);
          } else if (entry.isFile && (entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_') && !entry.name.includes('_layout')) {
            yamlFiles.push(entry);
          }
        }
        
        return yamlFiles;
      };
      
      const yamlFiles = await findYamlFiles(dialoguesPath);
      
      const loadedTrees: DialogueTree[] = [];
      
      for (const entry of yamlFiles) {
        try {
          const content = await window.daemonswright.fs.readFile(entry.path);
          const tree = parseDialogueFile(content, entry.path);
          if (tree) {
            // Try to load layout
            try {
              const layoutPath = entry.path.replace(/\.ya?ml$/, '_layout.yaml');
              const layoutContent = await window.daemonswright.fs.readFile(layoutPath);
              tree.layout = yaml.load(layoutContent) as Record<string, { x: number; y: number }>;
            } catch {
              // Layout doesn't exist, auto-layout will be used
            }
            loadedTrees.push(tree);
          }
        } catch (err) {
          console.warn(`Failed to load dialogue file ${entry.name}:`, err);
        }
      }
      
      setDialogueTrees(loadedTrees);
    } catch (err) {
      console.warn('Failed to load dialogues:', err);
      setDialogueTrees([]);
    }
  }, [worldDataPath]);

  // -------------------------------------------------------------------------
  // Main Load Function
  // -------------------------------------------------------------------------
  const reload = useCallback(async () => {
    if (!worldDataPath) return;
    
    setLoading(true);
    setError(null);
    
    try {
      await loadDialogues();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dialogues';
      setError(message);
      console.error('Failed to load dialogues:', err);
    } finally {
      setLoading(false);
    }
  }, [worldDataPath, loadDialogues]);

  // Load on mount when enabled
  useEffect(() => {
    if (enabled) {
      reload();
    }
  }, [reload, enabled]);

  // -------------------------------------------------------------------------
  // Selection
  // -------------------------------------------------------------------------
  const selectTree = useCallback((npcTemplateId: string | null) => {
    setSelectedTreeId(npcTemplateId);
  }, []);

  // -------------------------------------------------------------------------
  // Save Layout
  // -------------------------------------------------------------------------
  const saveLayout = useCallback(async () => {
    if (!selectedTree || !selectedTree.filePath) return;
    
    if (selectedTree.layout && Object.keys(selectedTree.layout).length > 0) {
      const layoutPath = selectedTree.filePath.replace(/\.ya?ml$/, '_layout.yaml');
      const content = yaml.dump(selectedTree.layout, { indent: 2 });
      await window.daemonswright.fs.writeFile(layoutPath, content);
    }
  }, [selectedTree]);

  // -------------------------------------------------------------------------
  // CRUD Operations
  // -------------------------------------------------------------------------
  const createDialogueTree = useCallback(async (treeData: Partial<DialogueTree>): Promise<boolean> => {
    if (!worldDataPath || !treeData.npc_template_id) return false;
    
    const newTree: DialogueTree = {
      npc_template_id: treeData.npc_template_id,
      entry_node: treeData.entry_node || 'greet',
      nodes: treeData.nodes || {
        greet: {
          text: 'Hello, traveler!',
          options: [
            { text: 'Hello!', next_node: null },
          ],
        },
      },
    };
    
    const filePath = `${worldDataPath}/dialogues/${newTree.npc_template_id}.yaml`;
    newTree.filePath = filePath;
    
    try {
      const content = serializeDialogue(newTree);
      await window.daemonswright.fs.writeFile(filePath, content);
      
      setDialogueTrees(prev => [...prev, newTree]);
      return true;
    } catch (err) {
      console.error('Failed to create dialogue tree:', err);
      return false;
    }
  }, [worldDataPath]);

  const updateDialogueTree = useCallback(async (npcTemplateId: string, updates: Partial<DialogueTree>): Promise<boolean> => {
    const tree = dialogueTrees.find(t => t.npc_template_id === npcTemplateId);
    if (!tree || !tree.filePath) return false;
    
    const updatedTree = { ...tree, ...updates };
    
    try {
      const content = serializeDialogue(updatedTree);
      await window.daemonswright.fs.writeFile(tree.filePath, content);
      
      setDialogueTrees(prev => prev.map(t => t.npc_template_id === npcTemplateId ? updatedTree : t));
      return true;
    } catch (err) {
      console.error('Failed to update dialogue tree:', err);
      return false;
    }
  }, [dialogueTrees]);

  const deleteDialogueTree = useCallback(async (npcTemplateId: string): Promise<boolean> => {
    const tree = dialogueTrees.find(t => t.npc_template_id === npcTemplateId);
    if (!tree || !tree.filePath) return false;
    
    try {
      await window.daemonswright.fs.deleteFile(tree.filePath);
      setDialogueTrees(prev => prev.filter(t => t.npc_template_id !== npcTemplateId));
      if (selectedTreeId === npcTemplateId) {
        setSelectedTreeId(null);
      }
      return true;
    } catch (err) {
      console.error('Failed to delete dialogue tree:', err);
      return false;
    }
  }, [dialogueTrees, selectedTreeId]);

  // -------------------------------------------------------------------------
  // Node Operations
  // -------------------------------------------------------------------------
  const addNode = useCallback(async (nodeId: string, node: Omit<DialogueNode, 'id'>): Promise<boolean> => {
    if (!selectedTree) return false;
    
    const updatedNodes = { ...selectedTree.nodes, [nodeId]: node };
    return updateDialogueTree(selectedTree.npc_template_id, { nodes: updatedNodes });
  }, [selectedTree, updateDialogueTree]);

  const updateNode = useCallback(async (nodeId: string, updates: Partial<DialogueNode>): Promise<boolean> => {
    if (!selectedTree || !selectedTree.nodes[nodeId]) return false;
    
    const updatedNodes = {
      ...selectedTree.nodes,
      [nodeId]: { ...selectedTree.nodes[nodeId], ...updates },
    };
    return updateDialogueTree(selectedTree.npc_template_id, { nodes: updatedNodes });
  }, [selectedTree, updateDialogueTree]);

  const deleteNode = useCallback(async (nodeId: string): Promise<boolean> => {
    if (!selectedTree) return false;
    
    const { [nodeId]: deleted, ...remainingNodes } = selectedTree.nodes;
    return updateDialogueTree(selectedTree.npc_template_id, { nodes: remainingNodes });
  }, [selectedTree, updateDialogueTree]);

  const updateNodePosition = useCallback((nodeId: string, position: { x: number; y: number }) => {
    if (!selectedTree) return;
    
    const updatedLayout = { ...(selectedTree.layout || {}), [nodeId]: position };
    setDialogueTrees(prev => prev.map(t => 
      t.npc_template_id === selectedTree.npc_template_id 
        ? { ...t, layout: updatedLayout } 
        : t
    ));
    // Debounce layout save
    setTimeout(() => saveLayout(), 500);
  }, [selectedTree, saveLayout]);

  // -------------------------------------------------------------------------
  // Connection Operations
  // -------------------------------------------------------------------------
  const addConnection = useCallback(async (
    sourceNodeId: string, 
    optionIndex: number, 
    targetNodeId: string
  ): Promise<boolean> => {
    if (!selectedTree || !selectedTree.nodes[sourceNodeId]) return false;
    
    const sourceNode = selectedTree.nodes[sourceNodeId];
    if (!sourceNode.options || optionIndex >= sourceNode.options.length) return false;
    
    const updatedOptions = [...sourceNode.options];
    updatedOptions[optionIndex] = { ...updatedOptions[optionIndex], next_node: targetNodeId };
    
    return updateNode(sourceNodeId, { options: updatedOptions });
  }, [selectedTree, updateNode]);

  const removeConnection = useCallback(async (
    sourceNodeId: string, 
    optionIndex: number
  ): Promise<boolean> => {
    if (!selectedTree || !selectedTree.nodes[sourceNodeId]) return false;
    
    const sourceNode = selectedTree.nodes[sourceNodeId];
    if (!sourceNode.options || optionIndex >= sourceNode.options.length) return false;
    
    const updatedOptions = [...sourceNode.options];
    updatedOptions[optionIndex] = { ...updatedOptions[optionIndex], next_node: null };
    
    return updateNode(sourceNodeId, { options: updatedOptions });
  }, [selectedTree, updateNode]);

  // -------------------------------------------------------------------------
  // Return Hook Result
  // -------------------------------------------------------------------------
  return {
    dialogueTrees,
    selectedTree,
    loading,
    error,
    
    selectTree,
    
    createDialogueTree,
    updateDialogueTree,
    deleteDialogueTree,
    
    addNode,
    updateNode,
    deleteNode,
    updateNodePosition,
    
    addConnection,
    removeConnection,
    
    reload,
  };
}
