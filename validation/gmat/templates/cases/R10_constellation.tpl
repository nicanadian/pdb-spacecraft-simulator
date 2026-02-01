%----------------------------------------
% R10: Constellation Script Regression Test
% Adapted from Ex_ConstellationScript.script
%
% Simplified constellation (2 SC) with reports
%----------------------------------------

%----------------------------------------
% Lead Spacecraft
%----------------------------------------
Create Spacecraft SC1;
GMAT SC1.DateFormat = UTCGregorian;
GMAT SC1.Epoch = '{{ epoch }}';
GMAT SC1.CoordinateSystem = EarthMJ2000Eq;
GMAT SC1.SMA = {{ sma_km | default(6878.137) }};
GMAT SC1.ECC = {{ ecc | default(0.0001) }};
GMAT SC1.INC = {{ inc_deg | default(53.0) }};
GMAT SC1.RAAN = {{ raan_deg | default(0.0) }};
GMAT SC1.AOP = {{ aop_deg | default(0.0) }};
GMAT SC1.TA = 0;
GMAT SC1.DryMass = {{ dry_mass_kg | default(450) }};
GMAT SC1.Cd = 2.2;
GMAT SC1.DragArea = {{ drag_area_m2 | default(5.0) }};

%----------------------------------------
% Trail Spacecraft
%----------------------------------------
Create Spacecraft SC2;
GMAT SC2.DateFormat = UTCGregorian;
GMAT SC2.Epoch = '{{ epoch }}';
GMAT SC2.CoordinateSystem = EarthMJ2000Eq;
GMAT SC2.SMA = {{ sma_km | default(6878.137) }};
GMAT SC2.ECC = {{ ecc | default(0.0001) }};
GMAT SC2.INC = {{ inc_deg | default(53.0) }};
GMAT SC2.RAAN = {{ raan_deg | default(0.0) }};
GMAT SC2.AOP = {{ aop_deg | default(0.0) }};
GMAT SC2.TA = 180;
GMAT SC2.DryMass = {{ dry_mass_kg | default(450) }};
GMAT SC2.Cd = 2.2;
GMAT SC2.DragArea = {{ drag_area_m2 | default(5.0) }};

%----------------------------------------
% Propagator
%----------------------------------------
Create ForceModel FM_Const;
GMAT FM_Const.CentralBody = Earth;
GMAT FM_Const.PrimaryBodies = {Earth};
GMAT FM_Const.GravityField.Earth.Degree = 4;
GMAT FM_Const.GravityField.Earth.Order = 4;
GMAT FM_Const.Drag = None;
GMAT FM_Const.SRP = Off;

Create Propagator Prop_Const;
GMAT Prop_Const.FM = FM_Const;
GMAT Prop_Const.Type = RungeKutta89;
GMAT Prop_Const.InitialStepSize = 60;
GMAT Prop_Const.Accuracy = 1e-12;

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

Create ReportFile KeplerianReport;
GMAT KeplerianReport.Filename = '{{ output_dir }}/keplerian_{{ case_id }}.txt';
GMAT KeplerianReport.Precision = 16;
GMAT KeplerianReport.WriteHeaders = true;

Create ReportFile TruthReport;
GMAT TruthReport.Filename = '{{ output_dir }}/truth_{{ case_id }}.txt';
GMAT TruthReport.Precision = 16;
GMAT TruthReport.WriteHeaders = true;
GMAT TruthReport.WriteReport = false;

Create ReportFile InitialStateReport;
GMAT InitialStateReport.Filename = '{{ output_dir }}/initial_{{ case_id }}.txt';
GMAT InitialStateReport.Precision = 16;
GMAT InitialStateReport.WriteHeaders = true;
GMAT InitialStateReport.WriteReport = false;

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

Toggle InitialStateReport On;
Report InitialStateReport SC1.UTCGregorian SC1.SMA SC1.ECC SC1.INC SC1.RAAN SC1.AOP SC1.TA SC1.TotalMass SC1.Altitude;
Report InitialStateReport SC2.UTCGregorian SC2.SMA SC2.ECC SC2.INC SC2.RAAN SC2.AOP SC2.TA SC2.TotalMass SC2.Altitude;
Toggle InitialStateReport Off;

While SC1.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport SC1.UTCGregorian SC1.EarthMJ2000Eq.X SC1.EarthMJ2000Eq.Y SC1.EarthMJ2000Eq.Z SC1.EarthMJ2000Eq.VX SC1.EarthMJ2000Eq.VY SC1.EarthMJ2000Eq.VZ;
    Report EphemerisReport SC2.UTCGregorian SC2.EarthMJ2000Eq.X SC2.EarthMJ2000Eq.Y SC2.EarthMJ2000Eq.Z SC2.EarthMJ2000Eq.VX SC2.EarthMJ2000Eq.VY SC2.EarthMJ2000Eq.VZ;
    Report KeplerianReport SC1.UTCGregorian SC1.SMA SC1.ECC SC1.INC SC1.RAAN SC1.AOP SC1.TA SC1.Altitude;
    Report KeplerianReport SC2.UTCGregorian SC2.SMA SC2.ECC SC2.INC SC2.RAAN SC2.AOP SC2.TA SC2.Altitude;
    Propagate Synchronized Prop_Const(SC1, SC2) {{"{"}}SC1.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

Toggle TruthReport On;
Report TruthReport SC1.UTCGregorian SC1.SMA SC1.ECC SC1.INC SC1.RAAN SC1.AOP SC1.TA SC1.TotalMass SC1.Altitude;
Report TruthReport SC2.UTCGregorian SC2.SMA SC2.ECC SC2.INC SC2.RAAN SC2.AOP SC2.TA SC2.TotalMass SC2.Altitude;
