%----------------------------------------
% N02: VLEO Continuous Drag Compensation
% NEW OPS-GRADE REFERENCE SCENARIO
%
% Continuous thrust balancing drag at 300 km VLEO
% - Continuous EP thrust (always on)
% - High-fidelity drag
% - Pinned atmosphere (fixed F107, Kp)
% - 3-day simulation
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
Create Spacecraft {{ spacecraft_name }};
GMAT {{ spacecraft_name }}.DateFormat = UTCGregorian;
GMAT {{ spacecraft_name }}.Epoch = '{{ epoch }}';
GMAT {{ spacecraft_name }}.CoordinateSystem = EarthMJ2000Eq;
GMAT {{ spacecraft_name }}.SMA = {{ sma_km | default(6678.137) }};
GMAT {{ spacecraft_name }}.ECC = {{ ecc | default(0.0001) }};
GMAT {{ spacecraft_name }}.INC = {{ inc_deg | default(53.0) }};
GMAT {{ spacecraft_name }}.RAAN = {{ raan_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.AOP = {{ aop_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.TA = {{ ta_deg | default(0.0) }};
GMAT {{ spacecraft_name }}.DryMass = {{ dry_mass_kg | default(450) }};
GMAT {{ spacecraft_name }}.Cd = 2.2;
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
GMAT EPThruster.ThrustDirection1 = 1;
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

Create FiniteBurn ContinuousBurn;
GMAT ContinuousBurn.Thrusters = {EPThruster};

%----------------------------------------
% Force Model with VLEO Drag
%----------------------------------------
Create ForceModel FM_VLEO;
GMAT FM_VLEO.CentralBody = Earth;
GMAT FM_VLEO.PrimaryBodies = {Earth};
GMAT FM_VLEO.GravityField.Earth.Degree = 20;
GMAT FM_VLEO.GravityField.Earth.Order = 20;
GMAT FM_VLEO.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_VLEO.Drag.AtmosphereModel = JacchiaRoberts;
GMAT FM_VLEO.Drag.F107 = {{ f107 | default(150) }};
GMAT FM_VLEO.Drag.F107A = {{ f107a | default(150) }};
GMAT FM_VLEO.SRP = Off;
GMAT FM_VLEO.ErrorControl = RSSStep;

Create Propagator Prop_VLEO;
GMAT Prop_VLEO.FM = FM_VLEO;
GMAT Prop_VLEO.Type = RungeKutta89;
GMAT Prop_VLEO.InitialStepSize = 30;
GMAT Prop_VLEO.Accuracy = 1e-10;
GMAT Prop_VLEO.MinStep = 0.001;
GMAT Prop_VLEO.MaxStep = 300;
GMAT Prop_VLEO.MaxStepAttempts = 100;
GMAT Prop_VLEO.StopIfAccuracyIsViolated = false;

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

Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Continuous thrust throughout
BeginFiniteBurn ContinuousBurn({{ spacecraft_name }});

While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.EPTank.FuelMass;
    Propagate Prop_VLEO({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s | default(60) }}{{"}"}};
EndWhile;

EndFiniteBurn ContinuousBurn({{ spacecraft_name }});

Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
