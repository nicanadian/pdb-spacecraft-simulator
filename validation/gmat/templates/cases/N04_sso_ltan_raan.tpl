%----------------------------------------
% N04: SSO LTAN/RAAN Maintenance
% NEW OPS-GRADE REFERENCE SCENARIO
%
% LTAN/RAAN control via out-of-plane EP thrust
% - Sun-synchronous orbit (97.4 deg inc)
% - Out-of-plane EP thrust arcs
% - RAAN targeting loop
% - 30-day simulation
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
Create Spacecraft {{ spacecraft_name }};
GMAT {{ spacecraft_name }}.DateFormat = UTCGregorian;
GMAT {{ spacecraft_name }}.Epoch = '{{ epoch }}';
GMAT {{ spacecraft_name }}.CoordinateSystem = EarthMJ2000Eq;
GMAT {{ spacecraft_name }}.SMA = {{ sma_km | default(7078.137) }};
GMAT {{ spacecraft_name }}.ECC = {{ ecc | default(0.0001) }};
GMAT {{ spacecraft_name }}.INC = {{ inc_deg | default(97.4) }};
GMAT {{ spacecraft_name }}.RAAN = {{ raan_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.AOP = {{ aop_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.TA = {{ ta_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.DryMass = {{ dry_mass_kg | default(450) }};
GMAT {{ spacecraft_name }}.Cd = 2.2;
GMAT {{ spacecraft_name }}.DragArea = {{ drag_area_m2 | default(5.0) }};
GMAT {{ spacecraft_name }}.SRPArea = {{ srp_area_m2 | default(10.0) }};

%----------------------------------------
% Electric Propulsion System (Out-of-plane)
%----------------------------------------
Create ElectricTank EPTank;
GMAT EPTank.AllowNegativeFuelMass = false;
GMAT EPTank.FuelMass = {{ propellant_kg | default(50.0) }};

Create ElectricThruster EPThruster;
GMAT EPThruster.CoordinateSystem = Local;
GMAT EPThruster.Origin = Earth;
GMAT EPThruster.Axes = VNB;
GMAT EPThruster.ThrustDirection1 = 0;
GMAT EPThruster.ThrustDirection2 = 1;   % Normal (out-of-plane)
GMAT EPThruster.ThrustDirection3 = 0;
GMAT EPThruster.DutyCycle = 1.0;
GMAT EPThruster.DecrementMass = true;
GMAT EPThruster.Tank = {EPTank};
GMAT EPThruster.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster.MaximumUsablePower = {{ max_power_kw | default(1.5) }};
GMAT EPThruster.ThrustCoeff1 = {{ thrust_mN | default(100) }};
GMAT EPThruster.Isp = {{ isp_s | default(1500) }};

GMAT {{ spacecraft_name }}.Tanks = {EPTank};
GMAT {{ spacecraft_name }}.Thrusters = {EPThruster};

Create FiniteBurn RAANBurn;
GMAT RAANBurn.Thrusters = {EPThruster};

%----------------------------------------
% Force Model
%----------------------------------------
Create ForceModel FM_SSO;
GMAT FM_SSO.CentralBody = Earth;
GMAT FM_SSO.PrimaryBodies = {Earth};
GMAT FM_SSO.PointMasses = {Luna, Sun};
GMAT FM_SSO.GravityField.Earth.Degree = 10;
GMAT FM_SSO.GravityField.Earth.Order = 10;
GMAT FM_SSO.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_SSO.Drag.AtmosphereModel = JacchiaRoberts;
GMAT FM_SSO.Drag.F107 = {{ f107 | default(150) }};
GMAT FM_SSO.Drag.F107A = {{ f107a | default(150) }};
GMAT FM_SSO.SRP = On;
GMAT FM_SSO.SRP.Flux = 1367.0;
GMAT FM_SSO.ErrorControl = RSSStep;

Create Propagator Prop_SSO;
GMAT Prop_SSO.FM = FM_SSO;
GMAT Prop_SSO.Type = RungeKutta89;
GMAT Prop_SSO.InitialStepSize = 60;
GMAT Prop_SSO.Accuracy = 1e-12;

%----------------------------------------
% Variables
%----------------------------------------
Create Variable InitialRAAN TargetRAAN RAANdrift;
GMAT InitialRAAN = 0;
GMAT TargetRAAN = 0;
GMAT RAANdrift = 0;

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

Create ReportFile MassReport;
GMAT MassReport.Filename = '{{ output_dir }}/mass_{{ case_id }}.txt';
GMAT MassReport.Precision = 16;
GMAT MassReport.WriteHeaders = true;

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

GMAT InitialRAAN = {{ spacecraft_name }}.RAAN;

Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    Propagate Prop_SSO({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s | default(60) }}{{"}"}};
EndWhile;

GMAT RAANdrift = {{ spacecraft_name }}.RAAN - InitialRAAN;

Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
