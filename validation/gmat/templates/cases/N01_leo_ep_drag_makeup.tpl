%----------------------------------------
% N01: LEO EP Drag Makeup
% NEW OPS-GRADE REFERENCE SCENARIO
%
% Maintain mean SMA under drag using EP finite burns at apogee
% - 500 km LEO orbit (SMA = 6878 km)
% - EP thruster: 100 mN, Isp 1500s
% - JacchiaRoberts drag (F107=150)
% - 10-day simulation
% - Thrust arcs at apogee to raise perigee
%
% Acceptance criteria:
% - Mean SMA drift approx 0 over window
% - Mass decreases per thrust profile
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
Create Spacecraft {{ spacecraft_name }};
GMAT {{ spacecraft_name }}.DateFormat = UTCGregorian;
GMAT {{ spacecraft_name }}.Epoch = '{{ epoch }}';
GMAT {{ spacecraft_name }}.CoordinateSystem = EarthMJ2000Eq;
GMAT {{ spacecraft_name }}.DisplayStateType = Keplerian;

% LEO Orbital Elements (500 km altitude)
GMAT {{ spacecraft_name }}.SMA = {{ sma_km | default(6878.137) }};
GMAT {{ spacecraft_name }}.ECC = {{ ecc | default(0.0001) }};
GMAT {{ spacecraft_name }}.INC = {{ inc_deg | default(53.0) }};
GMAT {{ spacecraft_name }}.RAAN = {{ raan_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.AOP = {{ aop_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.TA = {{ ta_deg | default(0.0) }};

% Physical Properties
GMAT {{ spacecraft_name }}.DryMass = {{ dry_mass_kg | default(450) }};
GMAT {{ spacecraft_name }}.Cd = 2.2;
GMAT {{ spacecraft_name }}.Cr = 1.8;
GMAT {{ spacecraft_name }}.DragArea = {{ drag_area_m2 | default(5.0) }};
GMAT {{ spacecraft_name }}.SRPArea = {{ srp_area_m2 | default(10.0) }};

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
GMAT EPThruster.ThrustDirection1 = 1;   % Prograde (raise orbit)
GMAT EPThruster.ThrustDirection2 = 0;
GMAT EPThruster.ThrustDirection3 = 0;
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
Create FiniteBurn DragMakeupBurn;
GMAT DragMakeupBurn.Thrusters = {EPThruster};
GMAT DragMakeupBurn.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

%----------------------------------------
% Force Model with Drag
%----------------------------------------
Create ForceModel FM_LEO;
GMAT FM_LEO.CentralBody = Earth;
GMAT FM_LEO.PrimaryBodies = {Earth};
GMAT FM_LEO.GravityField.Earth.Degree = {{ gravity_degree | default(10) }};
GMAT FM_LEO.GravityField.Earth.Order = {{ gravity_order | default(10) }};
GMAT FM_LEO.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_LEO.Drag.AtmosphereModel = JacchiaRoberts;
GMAT FM_LEO.Drag.F107 = {{ f107 | default(150) }};
GMAT FM_LEO.Drag.F107A = {{ f107a | default(150) }};
GMAT FM_LEO.SRP = Off;
GMAT FM_LEO.ErrorControl = RSSStep;

Create Propagator Prop_LEO;
GMAT Prop_LEO.FM = FM_LEO;
GMAT Prop_LEO.Type = {{ integrator_type | default('RungeKutta89') }};
GMAT Prop_LEO.InitialStepSize = {{ initial_step_s | default(60) }};
GMAT Prop_LEO.Accuracy = {{ accuracy | default(1e-10) }};
GMAT Prop_LEO.MinStep = {{ min_step_s | default(0.001) }};
GMAT Prop_LEO.MaxStep = {{ max_step_s | default(2700) }};
GMAT Prop_LEO.MaxStepAttempts = 100;
GMAT Prop_LEO.StopIfAccuracyIsViolated = false;

%----------------------------------------
% Control Variables
%----------------------------------------
Create Variable AltitudeThreshold BurnCount InitialSMA;
Create Variable CurrentSMA SMAdrift MinRadPer;
GMAT AltitudeThreshold = {{ altitude_threshold_km | default(498) }};
GMAT BurnCount = 0;
GMAT InitialSMA = 0;
GMAT CurrentSMA = 0;
GMAT SMAdrift = 0;
GMAT MinRadPer = {{ 6378.137 + (altitude_threshold_km | default(498)) }};

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

Create ReportFile EventReport;
GMAT EventReport.Filename = '{{ output_dir }}/events_{{ case_id }}.txt';
GMAT EventReport.Precision = 16;
GMAT EventReport.WriteHeaders = true;
GMAT EventReport.WriteReport = false;

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Record initial state
GMAT InitialSMA = {{ spacecraft_name }}.SMA;

% Capture initial state
Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Main drag makeup loop
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    % Report current state
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;

    % Check if we need to perform drag makeup burn
    % Burn at apogee when perigee altitude drops below threshold
    If {{ spacecraft_name }}.RadPer < MinRadPer
        % Propagate to apogee for efficient burn
        Propagate Prop_LEO({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};

        % Record burn start
        Toggle EventReport On;
        Report EventReport {{ spacecraft_name }}.UTCGregorian;

        GMAT BurnCount = BurnCount + 1;

        % Execute prograde burn to raise perigee
        BeginFiniteBurn DragMakeupBurn({{ spacecraft_name }});
        Propagate Prop_LEO({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ burn_duration_s | default(600) }}{{"}"}};
        EndFiniteBurn DragMakeupBurn({{ spacecraft_name }});

        % Record burn end
        Report EventReport {{ spacecraft_name }}.UTCGregorian;
        Toggle EventReport Off;

        % Report state after burn
        Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
        Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
        Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    EndIf;

    % Propagate one reporting step
    Propagate Prop_LEO({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s | default(60) }}{{"}"}};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;

% Calculate SMA drift
GMAT CurrentSMA = {{ spacecraft_name }}.SMA;
GMAT SMAdrift = CurrentSMA - InitialSMA;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
