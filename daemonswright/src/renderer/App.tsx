import { useState, useCallback, useEffect, useMemo } from 'react';
import { Layout, Drawer } from 'antd';
import { FileTree } from './components/FileTree';
import { AppLoader, InlineLoader, StartScreen } from './components/Loader';
import { ErrorPanel } from './components/ErrorPanel';
import React, { Suspense } from 'react';
// Ensure the lazily loaded module exposes a default React component for React.lazy
const YamlEditor = React.lazy(() =>
  import('./components/YamlEditor').then((mod) => ({ default: mod.YamlEditor }))
);
const RoomBuilder = React.lazy(() =>
  import('./components/RoomBuilder').then((mod) => ({ default: mod.RoomBuilder }))
);
const RoomPropertiesPanel = React.lazy(() =>
  import('./components/RoomBuilder/RoomPropertiesPanel').then((mod) => ({ default: mod.RoomPropertiesPanel }))
);
const ContentPalette = React.lazy(() =>
  import('./components/RoomBuilder/ContentPalette').then((mod) => ({ default: mod.ContentPalette }))
);
const EntityEditor = React.lazy(() =>
  import('./components/EntityEditor').then((mod) => ({ default: mod.EntityEditor }))
);
const QuestDesigner = React.lazy(() =>
  import('./components/QuestDesigner').then((mod) => ({ default: mod.QuestDesigner }))
);
const DialogueEditor = React.lazy(() =>
  import('./components/DialogueEditor').then((mod) => ({ default: mod.DialogueEditor }))
);
const WorldSummary = React.lazy(() =>
  import('./components/WorldSummary').then((mod) => ({ default: mod.WorldSummary }))
);
import { StatusBar } from './components/StatusBar';
import { MenuBar, EditorView } from './components/MenuBar';
import { useWorkspace } from './hooks/useWorkspace';
import { useSchema } from './hooks/useSchema';
import { useRoomBuilder } from './hooks/useRoomBuilder';
import { useRoomContents } from './hooks/useRoomContents';
import { useSchemaOptions } from './hooks/useSchemaOptions';
import { useReferenceValidation } from './hooks/useReferenceValidation';
import type { RoomNode } from '../shared/types';
import './styles/App.css';

const { Sider, Content, Footer } = Layout;

/**
 * Suspense fallback component for lazy-loaded editors
 */
function EditorFallback() {
  return (
    <div className="suspense-loader">
      <InlineLoader message="Loading editor..." />
    </div>
  );
}

function App() {
  // Track initial app loading state
  const [appReady, setAppReady] = useState(false);
  
  // Track last folder and recent folders for start screen
  const [lastFolder, setLastFolder] = useState<string | null>(null);
  const [recentFolders, setRecentFolders] = useState<string[]>([]);

  const {
    worldDataPath,
    openFolder,
    openFolderByPath,
    files,
    selectedFile,
    selectFile,
    fileContent,
    saveFile,
    isDirty,
    updateContent,
  } = useWorkspace();

  const { schemas, validationErrors: schemaErrors, validateContent, isLoading: schemasLoading } = useSchema(worldDataPath);

  // Reference validation
  const { 
    validationErrors: referenceErrors, 
    validateAll: validateReferences,
    isValidating: isValidatingReferences 
  } = useReferenceValidation(worldDataPath);

  // Combined validation errors
  const allValidationErrors = useMemo(
    () => [...schemaErrors, ...referenceErrors],
    [schemaErrors, referenceErrors]
  );

  // Current view mode (YAML editor or Room Builder)
  const [currentView, setCurrentView] = useState<EditorView>('yaml');

  // Entity editor category (for navigation from WorldSummary)
  const [entityEditorCategory, setEntityEditorCategory] = useState<string | undefined>(undefined);

  // Error panel drawer state
  const [errorPanelOpen, setErrorPanelOpen] = useState(false);

  // Room builder state
  const {
    rooms,
    connections,
    zLevels,
    updateRoomPosition,
    updateRoomProperties,
    createRoom,
    deleteRoom,
    addConnection,
    removeConnection,
    removeExit,
    createArea,
  } = useRoomBuilder(worldDataPath);

  // Room contents (NPCs and items) - only load when in room builder view
  const {
    npcSpawns,
    npcTemplates,
    itemInstances,
    itemTemplates,
    addNpcSpawn,
    updateNpcSpawn,
    removeNpcSpawn,
    addItemInstance,
    updateItemInstance,
    removeItemInstance,
  } = useRoomContents({ worldDataPath, enabled: currentView === 'room-builder' });

  // Schema options for dynamic field values
  const { roomOptions, areaOptions, addOption } = useSchemaOptions(worldDataPath);

  // Compute content counts per room for badges
  const roomContentCounts = useMemo(() => {
    const counts: Record<string, { npcCount: number; itemCount: number }> = {};
    
    // Count NPCs per room
    for (const spawn of npcSpawns) {
      if (spawn.room_id) {
        if (!counts[spawn.room_id]) {
          counts[spawn.room_id] = { npcCount: 0, itemCount: 0 };
        }
        counts[spawn.room_id].npcCount += spawn.quantity || 1;
      }
    }
    
    // Count items per room
    for (const instance of itemInstances) {
      if (instance.room_id) {
        if (!counts[instance.room_id]) {
          counts[instance.room_id] = { npcCount: 0, itemCount: 0 };
        }
        counts[instance.room_id].itemCount += instance.quantity || 1;
      }
    }
    
    return counts;
  }, [npcSpawns, itemInstances]);

  // Selected room for properties panel
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const selectedRoom = rooms.find((r) => r.id === selectedRoomId) || null;

  // Room property change tracking
  const [roomIsDirty, setRoomIsDirty] = useState(false);

  // Load last folder and recent folders on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const last = await window.daemonswright?.settings?.getLastFolder();
        const recent = await window.daemonswright?.settings?.getRecentFolders();
        setLastFolder(last || null);
        setRecentFolders(recent || []);
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    };
    loadSettings();
  }, []);

  const handleFileSelect = useCallback((filePath: string) => {
    selectFile(filePath);
  }, [selectFile]);

  // Handle navigation from WorldSummary to specific editors
  const handleWorldSummaryNavigate = useCallback((view: EditorView, category?: string) => {
    setCurrentView(view);
    if (view === 'entity-editor' && category) {
      setEntityEditorCategory(category);
    }
  }, []);

  // Validate when selected file or its content changes (including on first load)
  // But only after schemas have finished loading
  useEffect(() => {
    if (selectedFile && fileContent && !schemasLoading) {
      validateContent(fileContent, selectedFile);
    }
  }, [selectedFile, fileContent, validateContent, schemasLoading]);

  const handleContentChange = useCallback((content: string) => {
    // Update workspace state so file is marked dirty and content is stored
    updateContent(content);
    if (selectedFile && !schemasLoading) {
      validateContent(content, selectedFile);
    }
  }, [selectedFile, validateContent, updateContent, schemasLoading]);

  const handleSave = useCallback(async () => {
    if (selectedFile && fileContent) {
      await saveFile(selectedFile, fileContent);
    }
  }, [selectedFile, fileContent, saveFile]);

  // Listen for editor:save custom event (Cmd/Ctrl+S in Monaco)
  useEffect(() => {
    const onEditorSave = () => { handleSave(); };
    window.addEventListener('editor:save', onEditorSave);
    return () => window.removeEventListener('editor:save', onEditorSave);
  }, [handleSave]);

  // Mark app as ready once initial hooks have settled
  useEffect(() => {
    // Small delay to ensure all hooks have initialized
    const timer = setTimeout(() => {
      setAppReady(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // If no world is loaded, show the start screen
  if (!worldDataPath) {
    return (
      <StartScreen 
        onWorldSelect={openFolderByPath}
        lastFolder={lastFolder}
        recentFolders={recentFolders}
      />
    );
  }

  return (
    <AppLoader 
      isLoading={!appReady} 
      minDisplayTime={0} 
      message="Loading world data..."
    >
      <Layout className="app-layout">
        <MenuBar
          onOpenFolder={openFolder}
          onSave={handleSave}
          canSave={isDirty}
          currentView={currentView}
          onViewChange={setCurrentView}
        />

      <Layout className="main-layout">
        <Sider
          width={280}
          className="file-tree-sider"
          collapsible
          collapsedWidth={0}
        >
          <FileTree
            files={files}
            selectedFile={selectedFile}
            onSelect={handleFileSelect}
            worldDataPath={worldDataPath}
          />
        </Sider>

        <Content className="editor-content">
          {currentView === 'yaml' && selectedFile ? (
            <Suspense fallback={<EditorFallback />}>
              <YamlEditor
                filePath={selectedFile}
                content={fileContent}
                onChange={handleContentChange}
                validationErrors={allValidationErrors}
                schemas={schemas}
              />
            </Suspense>
          ) : currentView === 'room-builder' ? (
            <Layout style={{ height: '100%' }}>
              <Sider
                width={220}
                style={{ background: 'var(--color-bg-secondary)' }}
              >
                <Suspense fallback={<EditorFallback />}>
                  <ContentPalette
                    npcTemplates={npcTemplates}
                    itemTemplates={itemTemplates}
                  />
                </Suspense>
              </Sider>
              <Content style={{ flex: 1, minWidth: 0 }}>
                <Suspense fallback={<EditorFallback />}>
                  <RoomBuilder
                    rooms={rooms}
                    connections={connections}
                    zLevels={zLevels}
                    activeRoomId={selectedRoomId}
                    onRoomSelect={(roomId) => {
                      setSelectedRoomId(roomId);
                      setRoomIsDirty(false);
                    }}
                    onRoomMove={updateRoomPosition}
                    onRoomCreate={async (roomData, position, sourceRoomId) => {
                      return await createRoom(
                        {
                          id: roomData.id,
                          name: roomData.name,
                          description: roomData.description,
                          room_type: roomData.room_type,
                          area_id: roomData.area_id,
                          z_level: roomData.z_level,
                        },
                        position,
                        sourceRoomId
                      );
                    }}
                    onConnectionCreate={addConnection}
                    onConnectionDelete={removeConnection}
                    onRemoveExit={removeExit}
                    onAreaCreate={createArea}
                    roomTypeOptions={roomOptions.room_type || []}
                    onAddRoomType={async (newType) => {
                      return await addOption('room', 'room_type', newType);
                    }}
                    roomContentCounts={roomContentCounts}
                    onNpcDrop={async (roomId, npcTemplateId) => {
                      await addNpcSpawn(roomId, { npc_template_id: npcTemplateId });
                    }}
                    onItemDrop={async (roomId, itemTemplateId) => {
                      await addItemInstance(roomId, { item_template_id: itemTemplateId });
                    }}
                  />
                </Suspense>
              </Content>
              <Sider
                width={300}
                style={{ background: 'var(--color-bg-secondary)' }}
              >
                <Suspense fallback={<EditorFallback />}>
                  <RoomPropertiesPanel
                    selectedRoom={selectedRoom}
                    onSave={async (roomId, updates) => {
                      const success = await updateRoomProperties(roomId, updates);
                      if (success) {
                        setRoomIsDirty(false);
                      }
                    }}
                    onDelete={async (roomId) => {
                      const success = await deleteRoom(roomId);
                      if (success) {
                        setSelectedRoomId(null);
                      }
                    }}
                    onExitClick={(direction, targetId) => {
                      setSelectedRoomId(targetId);
                    }}
                    onAddExit={(roomId, direction, targetId) => {
                      addConnection(roomId, targetId, direction);
                    }}
                    onRemoveExit={async (roomId, direction) => {
                      await removeExit(roomId, direction);
                    }}
                    isDirty={roomIsDirty}
                    onDirtyChange={setRoomIsDirty}
                    roomTypeOptions={roomOptions.room_type || []}
                    onAddRoomType={async (newType) => {
                      return await addOption('room', 'room_type', newType);
                    }}
                    // NPC content
                    npcSpawns={npcSpawns}
                    npcTemplates={npcTemplates}
                    onAddNpcSpawn={addNpcSpawn}
                    onUpdateNpcSpawn={updateNpcSpawn}
                    onRemoveNpcSpawn={removeNpcSpawn}
                    // Item content
                    itemInstances={itemInstances}
                    itemTemplates={itemTemplates}
                    onAddItemInstance={addItemInstance}
                    onUpdateItemInstance={updateItemInstance}
                    onRemoveItemInstance={removeItemInstance}
                  />
                </Suspense>
              </Sider>
            </Layout>
          ) : currentView === 'entity-editor' ? (
            <Suspense fallback={<EditorFallback />}>
              <EntityEditor
                worldDataPath={worldDataPath}
                schemas={schemas}
                initialCategory={entityEditorCategory}
              />
            </Suspense>
          ) : currentView === 'quest-designer' ? (
            <Suspense fallback={<EditorFallback />}>
              <QuestDesigner
                worldDataPath={worldDataPath}
              />
            </Suspense>
          ) : currentView === 'dialogue-editor' ? (
            <Suspense fallback={<EditorFallback />}>
              <DialogueEditor
                worldDataPath={worldDataPath}
              />
            </Suspense>
          ) : (
            <Suspense fallback={<EditorFallback />}>
              <WorldSummary 
                worldDataPath={worldDataPath} 
                onNavigate={handleWorldSummaryNavigate}
              />
            </Suspense>
          )}
        </Content>
      </Layout>

      <Footer className="status-bar">
        <StatusBar
          filePath={selectedFile}
          isDirty={isDirty}
          validationErrors={allValidationErrors}
          isConnected={false}
          onErrorsClick={() => setErrorPanelOpen(true)}
        />
      </Footer>

      {/* Error Panel Drawer */}
      <Drawer
        title="Problems"
        placement="bottom"
        height={300}
        open={errorPanelOpen}
        onClose={() => setErrorPanelOpen(false)}
        className="error-panel-drawer"
      >
        <ErrorPanel 
          errors={allValidationErrors} 
          onRefresh={validateReferences}
          loading={isValidatingReferences}
        />
      </Drawer>
    </Layout>
    </AppLoader>
  );
}

export default App;
