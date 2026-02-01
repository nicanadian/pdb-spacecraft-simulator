%----------------------------------------
% R05: Force Models Regression Test
% Adapted from Ex_ForceModels.script
%
% Force model comparison (gravity, drag, SRP)
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Compares different force model configurations
% - Standard reports
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Force Model - Gravity Only
%----------------------------------------
Create ForceModel FM_GravityOnly;
GMAT FM_GravityOnly.CentralBody = Earth;
GMAT FM_GravityOnly.PrimaryBodies = {Earth};
GMAT FM_GravityOnly.GravityField.Earth.Degree = {{ gravity_degree | default(4) }};
GMAT FM_GravityOnly.GravityField.Earth.Order = {{ gravity_order | default(4) }};
GMAT FM_GravityOnly.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_GravityOnly.Drag = None;
GMAT FM_GravityOnly.SRP = Off;
GMAT FM_GravityOnly.ErrorControl = RSSStep;

Create Propagator Prop_GravityOnly;
GMAT Prop_GravityOnly.FM = FM_GravityOnly;
GMAT Prop_GravityOnly.Type = {{ integrator_type }};
GMAT Prop_GravityOnly.InitialStepSize = {{ initial_step_s }};
GMAT Prop_GravityOnly.Accuracy = {{ accuracy }};
GMAT Prop_GravityOnly.MinStep = {{ min_step_s }};
GMAT Prop_GravityOnly.MaxStep = {{ max_step_s }};

%----------------------------------------
% Force Model - Gravity + Drag
%----------------------------------------
Create ForceModel FM_GravityDrag;
GMAT FM_GravityDrag.CentralBody = Earth;
GMAT FM_GravityDrag.PrimaryBodies = {Earth};
GMAT FM_GravityDrag.GravityField.Earth.Degree = {{ gravity_degree | default(4) }};
GMAT FM_GravityDrag.GravityField.Earth.Order = {{ gravity_order | default(4) }};
GMAT FM_GravityDrag.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_GravityDrag.Drag.AtmosphereModel = JacchiaRoberts;
GMAT FM_GravityDrag.Drag.F107 = {{ f107 }};
GMAT FM_GravityDrag.Drag.F107A = {{ f107a }};
GMAT FM_GravityDrag.SRP = Off;
GMAT FM_GravityDrag.ErrorControl = RSSStep;

Create Propagator Prop_GravityDrag;
GMAT Prop_GravityDrag.FM = FM_GravityDrag;
GMAT Prop_GravityDrag.Type = {{ integrator_type }};
GMAT Prop_GravityDrag.InitialStepSize = {{ initial_step_s }};
GMAT Prop_GravityDrag.Accuracy = {{ accuracy }};
GMAT Prop_GravityDrag.MinStep = {{ min_step_s }};
GMAT Prop_GravityDrag.MaxStep = {{ max_step_s }};

%----------------------------------------
% Force Model - Gravity + Drag + SRP
%----------------------------------------
Create ForceModel FM_Full;
GMAT FM_Full.CentralBody = Earth;
GMAT FM_Full.PrimaryBodies = {Earth};
GMAT FM_Full.PointMasses = {Luna, Sun};
GMAT FM_Full.GravityField.Earth.Degree = {{ gravity_degree | default(4) }};
GMAT FM_Full.GravityField.Earth.Order = {{ gravity_order | default(4) }};
GMAT FM_Full.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_Full.Drag.AtmosphereModel = JacchiaRoberts;
GMAT FM_Full.Drag.F107 = {{ f107 }};
GMAT FM_Full.Drag.F107A = {{ f107a }};
GMAT FM_Full.SRP = On;
GMAT FM_Full.SRP.Flux = 1367.0;
GMAT FM_Full.SRP.SRPModel = Spherical;
GMAT FM_Full.ErrorControl = RSSStep;

Create Propagator Prop_Full;
GMAT Prop_Full.FM = FM_Full;
GMAT Prop_Full.Type = {{ integrator_type }};
GMAT Prop_Full.InitialStepSize = {{ initial_step_s }};
GMAT Prop_Full.Accuracy = {{ accuracy }};
GMAT Prop_Full.MinStep = {{ min_step_s }};
GMAT Prop_Full.MaxStep = {{ max_step_s }};

%----------------------------------------
% Output Reports
%----------------------------------------
Create ReportFile EphemerisReport;
GMAT EphemerisReport.Filename = '{{ output_dir }}/ephemeris_{{ case_id }}.txt';
GMAT EphemerisReport.Precision = 16;
GMAT EphemerisReport.WriteHeaders = true;
GMAT EphemerisReport.LeftJustify = On;
GMAT EphemerisReport.FixedWidth = true;
GMAT EphemerisReport.Delimiter = ' ';
GMAT EphemerisReport.ColumnWidth = 23;
GMAT EphemerisReport.WriteReport = true;

Create ReportFile KeplerianReport;
GMAT KeplerianReport.Filename = '{{ output_dir }}/keplerian_{{ case_id }}.txt';
GMAT KeplerianReport.Precision = 16;
GMAT KeplerianReport.WriteHeaders = true;
GMAT KeplerianReport.LeftJustify = On;
GMAT KeplerianReport.FixedWidth = true;
GMAT KeplerianReport.Delimiter = ' ';
GMAT KeplerianReport.ColumnWidth = 23;
GMAT KeplerianReport.WriteReport = true;

Create ReportFile TruthReport;
GMAT TruthReport.Filename = '{{ output_dir }}/truth_{{ case_id }}.txt';
GMAT TruthReport.Precision = 16;
GMAT TruthReport.WriteHeaders = true;
GMAT TruthReport.LeftJustify = On;
GMAT TruthReport.FixedWidth = true;
GMAT TruthReport.Delimiter = ' ';
GMAT TruthReport.ColumnWidth = 23;
GMAT TruthReport.WriteReport = false;

Create ReportFile InitialStateReport;
GMAT InitialStateReport.Filename = '{{ output_dir }}/initial_{{ case_id }}.txt';
GMAT InitialStateReport.Precision = 16;
GMAT InitialStateReport.WriteHeaders = true;
GMAT InitialStateReport.LeftJustify = On;
GMAT InitialStateReport.FixedWidth = true;
GMAT InitialStateReport.Delimiter = ' ';
GMAT InitialStateReport.ColumnWidth = 23;
GMAT InitialStateReport.WriteReport = false;

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Capture initial state
Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Propagate with full force model and report at intervals
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Propagate Prop_Full({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}, OrbitColor = Red{{"}"}};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
