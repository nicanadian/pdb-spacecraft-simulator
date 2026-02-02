/**
 * Tooltip - Hover tooltip component with glassmorphism styling
 */

import { Component, JSX, createSignal, Show } from 'solid-js';

interface TooltipProps {
  children: JSX.Element;
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
}

export const Tooltip: Component<TooltipProps> = (props) => {
  const [visible, setVisible] = createSignal(false);
  let timeoutId: number | undefined;

  const delay = props.delay ?? 300;
  const position = props.position ?? 'top';

  const showTooltip = () => {
    timeoutId = window.setTimeout(() => setVisible(true), delay);
  };

  const hideTooltip = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    setVisible(false);
  };

  return (
    <div
      class="tooltip-wrapper"
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
    >
      {props.children}

      <Show when={visible()}>
        <div class={`tooltip-content ${position}`}>
          {props.content}
        </div>
      </Show>

      <style>{`
        .tooltip-wrapper {
          position: relative;
          display: inline-flex;
        }

        .tooltip-content {
          position: absolute;
          padding: var(--space-2) var(--space-3);
          background: var(--deep-space-navy);
          color: var(--ghost-slate);
          font-size: var(--text-xs);
          border-radius: var(--radius-md);
          white-space: nowrap;
          z-index: var(--z-tooltip);
          pointer-events: none;
          box-shadow: var(--shadow-lg);
          animation: tooltip-fade-in 150ms ease;
        }

        .tooltip-content.top {
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
          margin-bottom: var(--space-2);
        }

        .tooltip-content.bottom {
          top: 100%;
          left: 50%;
          transform: translateX(-50%);
          margin-top: var(--space-2);
        }

        .tooltip-content.left {
          right: 100%;
          top: 50%;
          transform: translateY(-50%);
          margin-right: var(--space-2);
        }

        .tooltip-content.right {
          left: 100%;
          top: 50%;
          transform: translateY(-50%);
          margin-left: var(--space-2);
        }

        @keyframes tooltip-fade-in {
          from {
            opacity: 0;
            transform: translateX(-50%) translateY(4px);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }
      `}</style>
    </div>
  );
};
