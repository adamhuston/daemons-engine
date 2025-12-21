/**
 * YamlEditor Component
 *
 * Monaco-based YAML editor with schema-aware IntelliSense
 * and real-time validation.
 */

import Editor, { Monaco } from '@monaco-editor/react';
import { useCallback, useEffect, useRef, useMemo } from 'react';
import type { editor } from 'monaco-editor';
import type { SchemaDefinition, ValidationError } from '../../../shared/types';

interface YamlEditorProps {
  filePath: string;
  content: string;
  onChange: (content: string) => void;
  validationErrors: ValidationError[];
  schemas: Record<string, SchemaDefinition>;
  onNavigateToEntity?: (refType: string, entityId: string) => void;
}

export function YamlEditor({
  filePath,
  content,
  onChange,
  validationErrors,
  schemas,
  onNavigateToEntity,
}: YamlEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);

  // Infer content type from file path (moved up so it can be used in effects)
  const contentType = useMemo(() => 
    filePath.split(/[/\\]/).find((segment) =>
      ['rooms', 'items', 'npcs', 'quests', 'abilities', 'classes', 'areas', 'dialogues', 'triggers', 'factions', 'biomes', 'flora'].includes(segment)
    ),
    [filePath]
  );

  // Handle editor mount
  const handleEditorMount = useCallback(
    (editor: editor.IStandaloneCodeEditor, monaco: Monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Configure YAML language
      monaco.languages.register({ id: 'yaml' });

      // Set up keyboard shortcuts
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        // Trigger save - handled by parent
        const saveEvent = new CustomEvent('editor:save');
        window.dispatchEvent(saveEvent);
      });

      // Add Ctrl+Click jump to definition for reference fields
      if (onNavigateToEntity) {
        editor.onMouseDown((e) => {
          if (e.event.ctrlKey || e.event.metaKey) {
            const position = e.target.position;
            if (!position) return;

            const model = editor.getModel();
            if (!model) return;

            const lineContent = model.getLineContent(position.lineNumber);
            
            // Check for common reference patterns
            const patterns = [
              { regex: /npc_template_id:\s*["']?(\w+)["']?/, refType: 'npcs' },
              { regex: /item_template_id:\s*["']?(\w+)["']?/, refType: 'items' },
              { regex: /ability_id:\s*["']?(\w+)["']?/, refType: 'abilities' },
              { regex: /room_id:\s*["']?(\w+)["']?/, refType: 'rooms' },
              { regex: /quest_id:\s*["']?(\w+)["']?/, refType: 'quests' },
              { regex: /dialogue_id:\s*["']?(\w+)["']?/, refType: 'dialogues' },
              { regex: /template_id:\s*["']?(\w+)["']?/, refType: contentType || 'npcs' },
            ];

            for (const { regex, refType } of patterns) {
              const match = lineContent.match(regex);
              if (match) {
                onNavigateToEntity(refType, match[1]);
                break;
              }
            }
          }
        });
      }
    },
    [onNavigateToEntity, contentType]
  );

  // Register completion provider for enum values from schema
  useEffect(() => {
    if (!monacoRef.current || !contentType || !schemas[contentType]) return;

    const schema = schemas[contentType];
    const monaco = monacoRef.current;

    const provider = monaco.languages.registerCompletionItemProvider('yaml', {
      triggerCharacters: [' ', ':'],
      provideCompletionItems: (model: editor.ITextModel, position: { lineNumber: number; column: number }) => {
        const lineContent = model.getLineContent(position.lineNumber);
        // Check if we're after a field name (e.g., "biome: ")
        const fieldMatch = lineContent.match(/^(\w+):\s*/);
        if (!fieldMatch) return { suggestions: [] };

        const fieldName = fieldMatch[1];
        const field = schema.fields?.[fieldName];
        if (!field?.enum) return { suggestions: [] };

        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions = field.enum.map((value: string) => ({
          label: value,
          kind: monaco.languages.CompletionItemKind.EnumMember,
          insertText: value,
          range,
          detail: `${fieldName} option`,
        }));

        return { suggestions };
      },
    });

    return () => provider.dispose();
  }, [contentType, schemas]);

  // Register hover provider to show "Ctrl+Click to go to definition" for references
  useEffect(() => {
    if (!monacoRef.current || !onNavigateToEntity) return;

    const monaco = monacoRef.current;
    const referencePatterns = [
      /npc_template_id:\s*["']?(\w+)["']?/,
      /item_template_id:\s*["']?(\w+)["']?/,
      /ability_id:\s*["']?(\w+)["']?/,
      /room_id:\s*["']?(\w+)["']?/,
      /quest_id:\s*["']?(\w+)["']?/,
      /dialogue_id:\s*["']?(\w+)["']?/,
      /template_id:\s*["']?(\w+)["']?/,
    ];

    const hoverProvider = monaco.languages.registerHoverProvider('yaml', {
      provideHover: (model: editor.ITextModel, position: { lineNumber: number; column: number }) => {
        const lineContent = model.getLineContent(position.lineNumber);
        
        for (const pattern of referencePatterns) {
          const match = lineContent.match(pattern);
          if (match) {
            const valueStart = lineContent.indexOf(match[1]);
            const valueEnd = valueStart + match[1].length;
            
            // Check if cursor is on the value
            if (position.column >= valueStart && position.column <= valueEnd + 1) {
              return {
                range: {
                  startLineNumber: position.lineNumber,
                  endLineNumber: position.lineNumber,
                  startColumn: valueStart + 1,
                  endColumn: valueEnd + 1,
                },
                contents: [
                  { value: `**${match[1]}**` },
                  { value: 'Ctrl+Click to go to definition' },
                ],
              };
            }
          }
        }
        return null;
      },
    });

    return () => hoverProvider.dispose();
  }, [onNavigateToEntity]);

  // Update validation markers when errors change
  useEffect(() => {
    if (!monacoRef.current || !editorRef.current) return;

    const model = editorRef.current.getModel();
    if (!model) return;

    const markers = validationErrors.map((error) => ({
      severity: monacoRef.current!.MarkerSeverity.Error,
      message: error.message,
      startLineNumber: error.line ?? 1,
      startColumn: error.column ?? 1,
      endLineNumber: error.line ?? 1,
      endColumn: (error.column ?? 1) + 10,
    }));

    monacoRef.current.editor.setModelMarkers(model, 'yaml-validation', markers);
  }, [validationErrors]);

  return (
    <div className="yaml-editor">
      <div className="editor-header">
        <span className="file-path">{filePath}</span>
        {contentType && <span className="content-type">{contentType}</span>}
      </div>
      <Editor
        height="calc(100% - 32px)"
        language="yaml"
        value={content}
        theme="vs-dark"
        onChange={(value) => onChange(value ?? '')}
        onMount={handleEditorMount}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          wordWrap: 'on',
          automaticLayout: true,
          tabSize: 2,
          insertSpaces: true,
          formatOnPaste: true,
          scrollBeyondLastLine: false,
        }}
      />
    </div>
  );
}
