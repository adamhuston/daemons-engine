/**
 * ResizablePanel Component
 *
 * A wrapper that makes sidebars/panels resizable by dragging their edges.
 * Supports both left and right positioned panels.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { ReactNode, CSSProperties, MouseEvent } from 'react';
import './ResizablePanel.css';

interface ResizablePanelProps {
  /** Content to render inside the panel */
  children: ReactNode;
  /** Initial width of the panel in pixels */
  defaultWidth: number;
  /** Minimum width the panel can be resized to */
  minWidth?: number;
  /** Maximum width the panel can be resized to */
  maxWidth?: number;
  /** Position of the resize handle: 'left' or 'right' */
  resizeFrom: 'left' | 'right';
  /** Optional className for the panel container */
  className?: string;
  /** Optional inline styles */
  style?: CSSProperties;
  /** Callback when width changes */
  onWidthChange?: (width: number) => void;
  /** Storage key for persisting width */
  storageKey?: string;
}

export function ResizablePanel({
  children,
  defaultWidth,
  minWidth = 150,
  maxWidth = 600,
  resizeFrom,
  className = '',
  style = {},
  onWidthChange,
  storageKey,
}: ResizablePanelProps) {
  // Initialize width from localStorage if available
  const getInitialWidth = () => {
    if (storageKey) {
      const stored = localStorage.getItem(`resizable-panel-${storageKey}`);
      if (stored) {
        const parsed = parseInt(stored, 10);
        if (!isNaN(parsed) && parsed >= minWidth && parsed <= maxWidth) {
          return parsed;
        }
      }
    }
    return defaultWidth;
  };

  const [width, setWidth] = useState(getInitialWidth);
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  // Save width to localStorage
  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(`resizable-panel-${storageKey}`, String(width));
    }
  }, [width, storageKey]);

  const handleMouseDown = useCallback((e: MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    startXRef.current = e.clientX;
    startWidthRef.current = width;
  }, [width]);

  const handleMouseMove = useCallback((e: globalThis.MouseEvent) => {
    if (!isResizing) return;

    const delta = resizeFrom === 'right'
      ? e.clientX - startXRef.current
      : startXRef.current - e.clientX;

    const newWidth = Math.min(maxWidth, Math.max(minWidth, startWidthRef.current + delta));
    setWidth(newWidth);
    onWidthChange?.(newWidth);
  }, [isResizing, resizeFrom, minWidth, maxWidth, onWidthChange]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  // Attach global mouse listeners while resizing
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove as EventListener);
      document.addEventListener('mouseup', handleMouseUp);
      // Prevent text selection while resizing
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    } else {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove as EventListener);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={panelRef}
      className={`resizable-panel ${className} ${isResizing ? 'resizing' : ''}`}
      style={{
        ...style,
        width: `${width}px`,
        flexShrink: 0,
      }}
    >
      {/* Resize handle */}
      <div
        className={`resize-handle resize-handle-${resizeFrom}`}
        onMouseDown={handleMouseDown}
        title="Drag to resize"
      />

      {/* Panel content */}
      <div className="resizable-panel-content">
        {children}
      </div>
    </div>
  );
}
