%----------------------------------------
% R07: Attitude VNB Regression Test
% Adapted from Ex_Attitude_VNB.script
%
% VNB attitude-aligned thrust direction validation
% - Verifies thrust vector orientation in VNB frame
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Chemical Thruster with VNB Attitude
%----------------------------------------
Create ChemicalTank FuelTank;
GMAT FuelTank.AllowNegativeFuelMass = false;
GMAT FuelTank.FuelMass = {{ propellant_kg | default(50.0) }};
GMAT FuelTank.Pressure = 1500;
GMAT FuelTank.Temperature = 20;
GMAT FuelTank.RefTemperature = 20;
GMAT FuelTank.Volume = 0.075;
GMAT FuelTank.FuelDensity = 1260;
GMAT FuelTank.PressureModel = PressureRegulated;

% Thruster aligned with velocity direction (VNB)
Create ChemicalThruster VNBThruster;
GMAT VNBThruster.CoordinateSystem = Local;
GMAT VNBThruster.Origin = Earth;
GMAT VNBThruster.Axes = VNB;
GMAT VNBThruster.ThrustDirection1 = {{ thrust_dir_v | default(1) }};   % V (velocity)
GMAT VNBThruster.ThrustDirection2 = {{ thrust_dir_n | default(0) }};   % N (normal)
GMAT VNBThruster.ThrustDirection3 = {{ thrust_dir_b | default(0) }};   % B (binormal)
GMAT VNBThruster.DutyCycle = 1.0;
GMAT VNBThruster.ThrustScaleFactor = 1.0;
GMAT VNBThruster.DecrementMass = true;
GMAT VNBThruster.Tank = {FuelTank};
GMAT VNBThruster.MixRatio = [1];
GMAT VNBThruster.GravitationalAccel = 9.81;
GMAT VNBThruster.C1 = {{ thrust_n | default(500) }};
GMAT VNBThruster.K1 = {{ isp_chemical | default(300) }};

GMAT {{ spacecraft_name }}.Tanks = {FuelTank};
GMAT {{ spacecraft_name }}.Thrusters = {VNBThruster};

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn VNBBurn;
GMAT VNBBurn.Thrusters = {VNBThruster};
GMAT VNBBurn.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

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

Create ReportFile MassReport;
GMAT MassReport.Filename = '{{ output_dir }}/mass_{{ case_id }}.txt';
GMAT MassReport.Precision = 16;
GMAT MassReport.WriteHeaders = true;
GMAT MassReport.LeftJustify = On;
GMAT MassReport.FixedWidth = true;
GMAT MassReport.Delimiter = ' ';
GMAT MassReport.ColumnWidth = 23;
GMAT MassReport.WriteReport = true;

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

% Capture initial state
Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Report initial state
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Execute VNB-aligned burn at periapsis (raise apogee)
Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Periapsis{{"}"}};

Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Execute burn
BeginFiniteBurn VNBBurn({{ spacecraft_name }});
Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ burn_duration_s | default(30) }}{{"}"}};
EndFiniteBurn VNBBurn({{ spacecraft_name }});

Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Propagate remainder of scenario
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}, OrbitColor = Red{{"}"}};
EndWhile;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
