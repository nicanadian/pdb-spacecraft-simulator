/**
 * Resizable Panel - Draggable resize handle for panels
 */

import { Component, JSX, createSignal, onMount, onCleanup } from 'solid-js';

interface ResizablePanelProps {
  children: JSX.Element;
  initialWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  position: 'left' | 'right';
  class?: string;
}

export const ResizablePanel: Component<ResizablePanelProps> = (props) => {
  const [width, setWidth] = createSignal(props.initialWidth || 320);
  const [isResizing, setIsResizing] = createSignal(false);

  let panelRef: HTMLDivElement | undefined;

  const minWidth = props.minWidth || 200;
  const maxWidth = props.maxWidth || 600;

  const handleMouseDown = (e: MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing() || !panelRef) return;

    const rect = panelRef.getBoundingClientRect();
    let newWidth: number;

    if (props.position === 'left') {
      newWidth = e.clientX - rect.left;
    } else {
      newWidth = rect.right - e.clientX;
    }

    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    setWidth(newWidth);
  };

  const handleMouseUp = () => {
    setIsResizing(false);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  };

  onMount(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });

  onCleanup(() => {
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  });

  return (
    <div
      ref={panelRef}
      class={`resizable-panel ${props.class || ''}`}
      classList={{ resizing: isResizing() }}
      style={{ width: `${width()}px` }}
    >
      {props.children}

      <div
        class="resize-handle"
        classList={{ left: props.position === 'right', right: props.position === 'left' }}
        onMouseDown={handleMouseDown}
      />

      <style>{`
        .resizable-panel {
          position: relative;
          flex-shrink: 0;
        }

        .resizable-panel.resizing {
          user-select: none;
        }

        .resize-handle {
          position: absolute;
          top: 0;
          bottom: 0;
          width: 8px;
          cursor: col-resize;
          z-index: 10;
        }

        .resize-handle.left {
          left: -4px;
        }

        .resize-handle.right {
          right: -4px;
        }

        .resize-handle::before {
          content: '';
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 4px;
          height: 32px;
          background: var(--slate-300);
          border-radius: 2px;
          opacity: 0;
          transition: opacity var(--transition-fast);
        }

        .resize-handle:hover::before,
        .resizable-panel.resizing .resize-handle::before {
          opacity: 1;
        }
      `}</style>
    </div>
  );
};
