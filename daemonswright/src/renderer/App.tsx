import { useState, useCallback, useEffect } from 'react';
import { Layout } from 'antd';
import { FileTree } from './components/FileTree';
import React, { Suspense } from 'react';
// Ensure the lazily loaded module exposes a default React component for React.lazy
const YamlEditor = React.lazy(() =>
  import('./components/YamlEditor').then((mod) => ({ default: mod.YamlEditor }))
);
const RoomBuilder = React.lazy(() =>
  import('./components/RoomBuilder').then((mod) => ({ default: mod.RoomBuilder }))
);
import { StatusBar } from './components/StatusBar';
import { MenuBar, EditorView } from './components/MenuBar';
import { useWorkspace } from './hooks/useWorkspace';
import { useSchema } from './hooks/useSchema';
import { useRoomBuilder } from './hooks/useRoomBuilder';
import './styles/App.css';

const { Sider, Content, Footer } = Layout;

function App() {
  const {
    worldDataPath,
    openFolder,
    files,
    selectedFile,
    selectFile,
    fileContent,
    saveFile,
    isDirty,
    updateContent,
  } = useWorkspace();

  const { schemas, validationErrors, validateContent, isLoading: schemasLoading } = useSchema(worldDataPath);

  // Room builder state
  const {
    rooms,
    connections,
    zLevels,
    updateRoomPosition,
    addConnection,
    removeConnection,
  } = useRoomBuilder(worldDataPath);

  // Current view mode (YAML editor or Room Builder)
  const [currentView, setCurrentView] = useState<EditorView>('yaml');

  const handleFileSelect = useCallback((filePath: string) => {
    selectFile(filePath);
  }, [selectFile]);

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

  return (
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
            <Suspense fallback={<div className="editor-loading">Loading editor…</div>}>
              <YamlEditor
                filePath={selectedFile}
                content={fileContent}
                onChange={handleContentChange}
                validationErrors={validationErrors}
                schemas={schemas}
              />
            </Suspense>
          ) : currentView === 'room-builder' ? (
            <Suspense fallback={<div className="editor-loading">Loading Room Builder…</div>}>
              <RoomBuilder
                rooms={rooms}
                connections={connections}
                zLevels={zLevels}
                onRoomSelect={(roomId) => {
                  // Find the room file and open it in YAML editor
                  console.log('Selected room:', roomId);
                }}
                onRoomMove={updateRoomPosition}
                onConnectionCreate={addConnection}
                onConnectionDelete={removeConnection}
              />
            </Suspense>
          ) : (
            <div className="empty-state">
              <h2>Daemonswright Content Studio</h2>
              <p>Open a world_data folder to begin editing content</p>
            </div>
          )}
        </Content>
      </Layout>

      <Footer className="status-bar">
        <StatusBar
          filePath={selectedFile}
          isDirty={isDirty}
          validationErrors={validationErrors}
          isConnected={false}
        />
      </Footer>
    </Layout>
  );
}

export default App;
