%----------------------------------------
% Pure Propagation Validation Script
% Auto-generated for SGP4 vs numerical integration comparison
%
% Scenario: {{ scenario_name }}
% Duration: {{ duration_hours }} hours
% Start Epoch: {{ epoch }}
%----------------------------------------

%----------------------------------------
% Spacecraft
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Propagator
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Output Reports
%----------------------------------------
Create ReportFile EphemerisReport;
GMAT EphemerisReport.SolverIterations = Current;
GMAT EphemerisReport.UpperLeft = [0 0];
GMAT EphemerisReport.Size = [0 0];
GMAT EphemerisReport.RelativeZOrder = 0;
GMAT EphemerisReport.Maximized = false;
GMAT EphemerisReport.Filename = '{{ output_dir }}/ephemeris_{{ scenario_id }}.txt';
GMAT EphemerisReport.Precision = 16;
GMAT EphemerisReport.WriteHeaders = true;
GMAT EphemerisReport.LeftJustify = On;
GMAT EphemerisReport.ZeroFill = Off;
GMAT EphemerisReport.FixedWidth = true;
GMAT EphemerisReport.Delimiter = ' ';
GMAT EphemerisReport.ColumnWidth = 23;
GMAT EphemerisReport.WriteReport = true;

Create ReportFile KeplerianReport;
GMAT KeplerianReport.Filename = '{{ output_dir }}/keplerian_{{ scenario_id }}.txt';
GMAT KeplerianReport.Precision = 16;
GMAT KeplerianReport.WriteHeaders = true;
GMAT KeplerianReport.LeftJustify = On;
GMAT KeplerianReport.ZeroFill = Off;
GMAT KeplerianReport.FixedWidth = true;
GMAT KeplerianReport.Delimiter = ' ';
GMAT KeplerianReport.ColumnWidth = 23;
GMAT KeplerianReport.WriteReport = true;

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Propagate and report ephemeris at specified intervals
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{ '{' }}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}, OrbitColor = Red{{ '}' }};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
