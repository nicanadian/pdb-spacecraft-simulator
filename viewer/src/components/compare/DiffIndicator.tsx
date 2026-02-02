/**
 * Diff Indicator - Shows delta between values with visual encoding
 */

import { Component, Show } from 'solid-js';

interface DiffIndicatorProps {
  current: number;
  baseline: number;
  unit: string;
  label: string;
  format?: (value: number) => string;
  positiveIsGood?: boolean;
}

export const DiffIndicator: Component<DiffIndicatorProps> = (props) => {
  const format = props.format || ((v: number) => v.toFixed(2));

  const delta = () => props.current - props.baseline;
  const percentChange = () => {
    if (props.baseline === 0) return 0;
    return ((props.current - props.baseline) / Math.abs(props.baseline)) * 100;
  };

  const isPositive = () => delta() > 0;
  const isNegative = () => delta() < 0;
  const isNeutral = () => Math.abs(delta()) < 0.001;

  const severity = () => {
    if (isNeutral()) return 'neutral';
    const positive = props.positiveIsGood ?? true;
    if ((isPositive() && positive) || (isNegative() && !positive)) {
      return 'positive';
    }
    return 'negative';
  };

  return (
    <div class="diff-indicator">
      <div class="diff-header">
        <span class="diff-label">{props.label}</span>
        <span class="diff-current font-mono">
          {format(props.current)} {props.unit}
        </span>
      </div>

      <Show when={!isNeutral()}>
        <div class={`diff-delta ${severity()}`}>
          <span class="delta-arrow">{isPositive() ? '\u2191' : '\u2193'}</span>
          <span class="delta-value font-mono">
            {isPositive() ? '+' : ''}{format(delta())} {props.unit}
          </span>
          <span class="delta-percent font-mono">
            ({percentChange().toFixed(1)}%)
          </span>
          <span class="delta-label">vs baseline</span>
        </div>
      </Show>

      <Show when={isNeutral()}>
        <div class="diff-delta neutral">
          <span class="delta-label">No change from baseline</span>
        </div>
      </Show>

      <style>{`
        .diff-indicator {
          padding: var(--space-3);
          background: white;
          border: 1px solid var(--neutral-border);
          border-radius: var(--radius-md);
        }

        .diff-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--space-2);
        }

        .diff-label {
          font-size: var(--text-xs);
          color: var(--slate-500);
        }

        .diff-current {
          font-size: var(--text-sm);
          font-weight: var(--font-semibold);
          color: var(--slate-800);
        }

        .diff-delta {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding: var(--space-2);
          border-radius: var(--radius-sm);
          font-size: var(--text-xs);
        }

        .diff-delta.positive {
          background: var(--alert-success-bg);
          color: var(--alert-success);
        }

        .diff-delta.negative {
          background: var(--alert-failure-bg);
          color: var(--alert-failure);
        }

        .diff-delta.neutral {
          background: var(--slate-100);
          color: var(--slate-500);
        }

        .delta-arrow {
          font-weight: bold;
        }

        .delta-value {
          font-weight: var(--font-medium);
        }

        .delta-percent {
          opacity: 0.8;
        }

        .delta-label {
          margin-left: auto;
          opacity: 0.7;
        }
      `}</style>
    </div>
  );
};
