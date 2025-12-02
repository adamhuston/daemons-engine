import { useState, useCallback } from 'react';
import { Layout } from 'antd';
import { FileTree } from './components/FileTree';
import { YamlEditor } from './components/YamlEditor';
import { StatusBar } from './components/StatusBar';
import { MenuBar } from './components/MenuBar';
import { useWorkspace } from './hooks/useWorkspace';
import { useSchema } from './hooks/useSchema';
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
  } = useWorkspace();

  const { schemas, validationErrors, validateContent } = useSchema(worldDataPath);

  const handleFileSelect = useCallback((filePath: string) => {
    selectFile(filePath);
  }, [selectFile]);

  const handleContentChange = useCallback((content: string) => {
    if (selectedFile) {
      validateContent(content, selectedFile);
    }
  }, [selectedFile, validateContent]);

  const handleSave = useCallback(async () => {
    if (selectedFile && fileContent) {
      await saveFile(selectedFile, fileContent);
    }
  }, [selectedFile, fileContent, saveFile]);

  return (
    <Layout className="app-layout">
      <MenuBar
        onOpenFolder={openFolder}
        onSave={handleSave}
        canSave={isDirty}
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
          {selectedFile ? (
            <YamlEditor
              filePath={selectedFile}
              content={fileContent}
              onChange={handleContentChange}
              validationErrors={validationErrors}
              schemas={schemas}
            />
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
