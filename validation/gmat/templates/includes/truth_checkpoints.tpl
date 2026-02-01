%----------------------------------------
% Truth Checkpoint Capture
% Include this template for final state capture for regression validation
%----------------------------------------

%----------------------------------------
% Truth Report (Final State Capture)
%----------------------------------------
Create ReportFile TruthReport;
GMAT TruthReport.SolverIterations = Current;
GMAT TruthReport.UpperLeft = [0 0];
GMAT TruthReport.Size = [0 0];
GMAT TruthReport.RelativeZOrder = 0;
GMAT TruthReport.Maximized = false;
GMAT TruthReport.Filename = '{{ output_dir }}/truth_{{ case_id }}.txt';
GMAT TruthReport.Precision = 16;
GMAT TruthReport.WriteHeaders = true;
GMAT TruthReport.LeftJustify = On;
GMAT TruthReport.ZeroFill = Off;
GMAT TruthReport.FixedWidth = true;
GMAT TruthReport.Delimiter = ' ';
GMAT TruthReport.ColumnWidth = 23;
GMAT TruthReport.WriteReport = false;  % Only written at checkpoints

{% if capture_initial %}
%----------------------------------------
% Initial State Report (Capture at epoch)
%----------------------------------------
Create ReportFile InitialStateReport;
GMAT InitialStateReport.SolverIterations = Current;
GMAT InitialStateReport.Filename = '{{ output_dir }}/initial_{{ case_id }}.txt';
GMAT InitialStateReport.Precision = 16;
GMAT InitialStateReport.WriteHeaders = true;
GMAT InitialStateReport.LeftJustify = On;
GMAT InitialStateReport.ZeroFill = Off;
GMAT InitialStateReport.FixedWidth = true;
GMAT InitialStateReport.Delimiter = ' ';
GMAT InitialStateReport.ColumnWidth = 23;
GMAT InitialStateReport.WriteReport = false;  % Written once at start
{% endif %}

%----------------------------------------
% Truth Checkpoint Macro
% Add this at the END of mission sequence to capture final state
%----------------------------------------
% Toggle TruthReport On;
% Report TruthReport {{ sc_name }}.UTCGregorian {{ sc_name }}.SMA {{ sc_name }}.ECC {{ sc_name }}.INC {{ sc_name }}.RAAN {{ sc_name }}.AOP {{ sc_name }}.TA {{ sc_name }}.TotalMass {{ sc_name }}.Altitude;
% Report TruthReport {{ sc_name }}.UTCGregorian {{ sc_name }}.EarthMJ2000Eq.X {{ sc_name }}.EarthMJ2000Eq.Y {{ sc_name }}.EarthMJ2000Eq.Z {{ sc_name }}.EarthMJ2000Eq.VX {{ sc_name }}.EarthMJ2000Eq.VY {{ sc_name }}.EarthMJ2000Eq.VZ;

%----------------------------------------
% Initial State Macro (call at start of mission sequence)
%----------------------------------------
% Toggle InitialStateReport On;
% Report InitialStateReport {{ sc_name }}.UTCGregorian {{ sc_name }}.SMA {{ sc_name }}.ECC {{ sc_name }}.INC {{ sc_name }}.RAAN {{ sc_name }}.AOP {{ sc_name }}.TA {{ sc_name }}.TotalMass {{ sc_name }}.Altitude;
% Report InitialStateReport {{ sc_name }}.UTCGregorian {{ sc_name }}.EarthMJ2000Eq.X {{ sc_name }}.EarthMJ2000Eq.Y {{ sc_name }}.EarthMJ2000Eq.Z {{ sc_name }}.EarthMJ2000Eq.VX {{ sc_name }}.EarthMJ2000Eq.VY {{ sc_name }}.EarthMJ2000Eq.VZ;
% Toggle InitialStateReport Off;
