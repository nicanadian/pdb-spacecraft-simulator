%----------------------------------------
% R04: Electric Propulsion Modeling Regression Test
% Adapted from Tut_ElectricPropulsionModelling.script
%
% EP modeling converted to LEO with drag
% - Electric thruster with finite burns
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
Create Spacecraft {{ spacecraft_name }};
GMAT {{ spacecraft_name }}.DateFormat = UTCGregorian;
GMAT {{ spacecraft_name }}.Epoch = '{{ epoch }}';
GMAT {{ spacecraft_name }}.CoordinateSystem = EarthMJ2000Eq;
GMAT {{ spacecraft_name }}.DisplayStateType = Keplerian;

% Orbital Elements
GMAT {{ spacecraft_name }}.SMA = {{ sma_km }};
GMAT {{ spacecraft_name }}.ECC = {{ ecc }};
GMAT {{ spacecraft_name }}.INC = {{ inc_deg }};
GMAT {{ spacecraft_name }}.RAAN = {{ raan_deg }};
GMAT {{ spacecraft_name }}.AOP = {{ aop_deg }};
GMAT {{ spacecraft_name }}.TA = {{ ta_deg }};

% Physical Properties
GMAT {{ spacecraft_name }}.DryMass = {{ dry_mass_kg }};
GMAT {{ spacecraft_name }}.Cd = 2.2;
GMAT {{ spacecraft_name }}.Cr = 1.8;
GMAT {{ spacecraft_name }}.DragArea = {{ drag_area_m2 }};
GMAT {{ spacecraft_name }}.SRPArea = {{ srp_area_m2 }};

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
GMAT EPThruster.ThrustDirection1 = {{ thrust_dir_1 | default(-1) }};  % Retrograde for orbit lowering
GMAT EPThruster.ThrustDirection2 = {{ thrust_dir_2 | default(0) }};
GMAT EPThruster.ThrustDirection3 = {{ thrust_dir_3 | default(0) }};
GMAT EPThruster.DutyCycle = 1.0;
GMAT EPThruster.ThrustScaleFactor = 1.0;
GMAT EPThruster.DecrementMass = true;
GMAT EPThruster.Tank = {EPTank};
GMAT EPThruster.MixRatio = [1];
GMAT EPThruster.GravitationalAccel = 9.81;
GMAT EPThruster.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster.MaximumUsablePower = {{ max_power_kw | default(1.5) }};
GMAT EPThruster.MinimumUsablePower = 0.001;
GMAT EPThruster.ThrustCoeff1 = {{ thrust_mN | default(100) }};
GMAT EPThruster.ThrustCoeff2 = 0.0;
GMAT EPThruster.ThrustCoeff3 = 0.0;
GMAT EPThruster.ThrustCoeff4 = 0.0;
GMAT EPThruster.ThrustCoeff5 = 0.0;
GMAT EPThruster.MassFlowCoeff1 = {{ mass_flow_coeff | default(0.0068) }};
GMAT EPThruster.MassFlowCoeff2 = 0.0;
GMAT EPThruster.MassFlowCoeff3 = 0.0;
GMAT EPThruster.MassFlowCoeff4 = 0.0;
GMAT EPThruster.MassFlowCoeff5 = 0.0;
GMAT EPThruster.Isp = {{ isp_s | default(1500) }};

GMAT {{ spacecraft_name }}.Tanks = {EPTank};
GMAT {{ spacecraft_name }}.Thrusters = {EPThruster};

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn EPBurn;
GMAT EPBurn.Thrusters = {EPThruster};
GMAT EPBurn.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

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
% Variables for thrust arc control
%----------------------------------------
Create Variable ThrustArcCounter OrbitCounter;
GMAT ThrustArcCounter = 0;
GMAT OrbitCounter = 0;

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Capture initial state
Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Main simulation loop with periodic EP burns
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    % Report current state
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;

    % Execute EP burn at apogee (to lower perigee for orbit lowering)
    If {{ spacecraft_name }}.TA > 170 & {{ spacecraft_name }}.TA < 190
        GMAT ThrustArcCounter = ThrustArcCounter + 1;

        % EP burn for {{ ep_burn_duration_s | default(300) }} seconds
        BeginFiniteBurn EPBurn({{ spacecraft_name }});
        Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ ep_burn_duration_s | default(300) }}{{"}"}};
        EndFiniteBurn EPBurn({{ spacecraft_name }});

        Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
        Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
        Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    EndIf;

    % Propagate one step
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
