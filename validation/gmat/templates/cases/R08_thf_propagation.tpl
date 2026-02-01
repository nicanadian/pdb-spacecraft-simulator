%----------------------------------------
% R08: Thrust Profile Propagation Regression Test
% Simplified from Ex_R2020a_Propagate_ThrustHistoryFile.script
%
% EP thrust profile propagation with mass/state reports
% - Uses finite burn for thrust profile (simplified from THF)
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Electric Propulsion System
%----------------------------------------
Create ElectricTank EPTank;
GMAT EPTank.AllowNegativeFuelMass = false;
GMAT EPTank.FuelMass = {{ propellant_kg | default(50.0) }};

Create ElectricThruster EPThruster;
GMAT EPThruster.CoordinateSystem = Local;
GMAT EPThruster.Origin = Earth;
GMAT EPThruster.Axes = VNB;
GMAT EPThruster.ThrustDirection1 = 1;   % Prograde
GMAT EPThruster.ThrustDirection2 = 0;
GMAT EPThruster.ThrustDirection3 = 0;
GMAT EPThruster.DutyCycle = 1.0;
GMAT EPThruster.DecrementMass = true;
GMAT EPThruster.Tank = {EPTank};
GMAT EPThruster.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster.MaximumUsablePower = {{ max_power_kw | default(1.5) }};
GMAT EPThruster.ThrustCoeff1 = {{ thrust_mN | default(100) }};
GMAT EPThruster.Isp = {{ isp_s | default(1500) }};

%----------------------------------------
% Solar Power System (required for EP)
%----------------------------------------
Create SolarPowerSystem SolarArrays;
GMAT SolarArrays.EpochFormat = 'UTCGregorian';
GMAT SolarArrays.InitialEpoch = '{{ epoch }}';
GMAT SolarArrays.InitialMaxPower = {{ max_power_kw | default(2.0) }};
GMAT SolarArrays.AnnualDecayRate = 1;
GMAT SolarArrays.Margin = 5;
GMAT SolarArrays.BusCoeff1 = 0.3;
GMAT SolarArrays.BusCoeff2 = 0;
GMAT SolarArrays.BusCoeff3 = 0;
GMAT SolarArrays.ShadowModel = 'DualCone';
GMAT SolarArrays.ShadowBodies = {'Earth'};

GMAT {{ spacecraft_name }}.Tanks = {EPTank};
GMAT {{ spacecraft_name }}.Thrusters = {EPThruster};
GMAT {{ spacecraft_name }}.PowerSystem = SolarArrays;

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn ThrustBurn;
GMAT ThrustBurn.Thrusters = {EPThruster};

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Control Variables
%----------------------------------------
Create Variable BurnPhase ThrustActive;
GMAT BurnPhase = 0;
GMAT ThrustActive = 1;

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

% Phase 1: Thrust for first portion of simulation (simulating THF profile)
BeginFiniteBurn ThrustBurn({{ spacecraft_name }});

While {{ spacecraft_name }}.ElapsedSecs < {{ thrust_duration_s | default(3600) }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

EndFiniteBurn ThrustBurn({{ spacecraft_name }});

% Phase 2: Coast for remainder of simulation
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
