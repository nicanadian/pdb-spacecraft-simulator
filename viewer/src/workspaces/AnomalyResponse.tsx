/**
 * Anomaly Response Workspace
 * Root cause analysis and recovery operations
 */

import { Component } from 'solid-js';
import { AlertCenter } from '@/components/alerts/AlertCenter';

export const AnomalyResponse: Component = () => {
  return (
    <div class="anomaly-workspace">
      <AlertCenter />

      <style>{`
        .anomaly-workspace {
          height: 100%;
          overflow: hidden;
        }
      `}</style>
    </div>
  );
};
