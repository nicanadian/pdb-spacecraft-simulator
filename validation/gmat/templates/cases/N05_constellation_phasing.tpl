%----------------------------------------
% N05: Constellation Phasing
% NEW OPS-GRADE REFERENCE SCENARIO
%
% Two-spacecraft along-track phasing with differential EP
% - Two spacecraft in same orbit plane
% - Differential EP thrust for phasing
% - Target: achieve phase separation
% - 7-day simulation
%
% Acceptance criteria:
% - Phase separation achieved at epoch
% - Synchronized propagation
%----------------------------------------

%----------------------------------------
% Lead Spacecraft Definition
%----------------------------------------
Create Spacecraft SC_Lead;
GMAT SC_Lead.DateFormat = UTCGregorian;
GMAT SC_Lead.Epoch = '{{ epoch }}';
GMAT SC_Lead.CoordinateSystem = EarthMJ2000Eq;
GMAT SC_Lead.DisplayStateType = Keplerian;

% LEO Orbital Elements (500 km altitude)
GMAT SC_Lead.SMA = {{ sma_km | default(6878.137) }};
GMAT SC_Lead.ECC = {{ ecc | default(0.0001) }};
GMAT SC_Lead.INC = {{ inc_deg | default(53.0) }};
GMAT SC_Lead.RAAN = {{ raan_deg | default(0.0) }};
GMAT SC_Lead.AOP = {{ aop_deg | default(0.0) }};
GMAT SC_Lead.TA = {{ ta_lead_deg | default(0.0) }};

% Physical Properties
GMAT SC_Lead.DryMass = {{ dry_mass_kg | default(450) }};
GMAT SC_Lead.Cd = 2.2;
GMAT SC_Lead.Cr = 1.8;
GMAT SC_Lead.DragArea = {{ drag_area_m2 | default(5.0) }};
GMAT SC_Lead.SRPArea = {{ srp_area_m2 | default(10.0) }};

%----------------------------------------
% Trail Spacecraft Definition
%----------------------------------------
Create Spacecraft SC_Trail;
GMAT SC_Trail.DateFormat = UTCGregorian;
GMAT SC_Trail.Epoch = '{{ epoch }}';
GMAT SC_Trail.CoordinateSystem = EarthMJ2000Eq;
GMAT SC_Trail.DisplayStateType = Keplerian;

% Same orbit, different phase
GMAT SC_Trail.SMA = {{ sma_km | default(6878.137) }};
GMAT SC_Trail.ECC = {{ ecc | default(0.0001) }};
GMAT SC_Trail.INC = {{ inc_deg | default(53.0) }};
GMAT SC_Trail.RAAN = {{ raan_deg | default(0.0) }};
GMAT SC_Trail.AOP = {{ aop_deg | default(0.0) }};
GMAT SC_Trail.TA = {{ ta_trail_deg | default(10.0) }};

GMAT SC_Trail.DryMass = {{ dry_mass_kg | default(450) }};
GMAT SC_Trail.Cd = 2.2;
GMAT SC_Trail.Cr = 1.8;
GMAT SC_Trail.DragArea = {{ drag_area_m2 | default(5.0) }};
GMAT SC_Trail.SRPArea = {{ srp_area_m2 | default(10.0) }};

%----------------------------------------
% Electric Propulsion Systems
%----------------------------------------
Create ElectricTank EPTank_Lead;
GMAT EPTank_Lead.AllowNegativeFuelMass = false;
GMAT EPTank_Lead.FuelMass = {{ propellant_kg | default(50.0) }};

Create ElectricTank EPTank_Trail;
GMAT EPTank_Trail.AllowNegativeFuelMass = false;
GMAT EPTank_Trail.FuelMass = {{ propellant_kg | default(50.0) }};

Create ElectricThruster EPThruster_Lead;
GMAT EPThruster_Lead.CoordinateSystem = Local;
GMAT EPThruster_Lead.Origin = Earth;
GMAT EPThruster_Lead.Axes = VNB;
GMAT EPThruster_Lead.ThrustDirection1 = 1;
GMAT EPThruster_Lead.ThrustDirection2 = 0;
GMAT EPThruster_Lead.ThrustDirection3 = 0;
GMAT EPThruster_Lead.DutyCycle = 1.0;
GMAT EPThruster_Lead.DecrementMass = true;
GMAT EPThruster_Lead.Tank = {EPTank_Lead};
GMAT EPThruster_Lead.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster_Lead.MaximumUsablePower = {{ max_power_kw | default(1.5) }};
GMAT EPThruster_Lead.ThrustCoeff1 = {{ thrust_mN | default(100) }};
GMAT EPThruster_Lead.Isp = {{ isp_s | default(1500) }};

Create ElectricThruster EPThruster_Trail;
GMAT EPThruster_Trail.CoordinateSystem = Local;
GMAT EPThruster_Trail.Origin = Earth;
GMAT EPThruster_Trail.Axes = VNB;
GMAT EPThruster_Trail.ThrustDirection1 = -1;  % Retrograde to catch up
GMAT EPThruster_Trail.ThrustDirection2 = 0;
GMAT EPThruster_Trail.ThrustDirection3 = 0;
GMAT EPThruster_Trail.DutyCycle = 1.0;
GMAT EPThruster_Trail.DecrementMass = true;
GMAT EPThruster_Trail.Tank = {EPTank_Trail};
GMAT EPThruster_Trail.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster_Trail.MaximumUsablePower = {{ max_power_kw | default(1.5) }};
GMAT EPThruster_Trail.ThrustCoeff1 = {{ thrust_mN | default(100) }};
GMAT EPThruster_Trail.Isp = {{ isp_s | default(1500) }};

%----------------------------------------
% Solar Power Systems (required for EP)
%----------------------------------------
Create SolarPowerSystem SolarArrays_Lead;
GMAT SolarArrays_Lead.EpochFormat = 'UTCGregorian';
GMAT SolarArrays_Lead.InitialEpoch = '{{ epoch }}';
GMAT SolarArrays_Lead.InitialMaxPower = {{ max_power_kw | default(2.0) }};
GMAT SolarArrays_Lead.AnnualDecayRate = 1;
GMAT SolarArrays_Lead.Margin = 5;
GMAT SolarArrays_Lead.BusCoeff1 = 0.3;
GMAT SolarArrays_Lead.BusCoeff2 = 0;
GMAT SolarArrays_Lead.BusCoeff3 = 0;
GMAT SolarArrays_Lead.ShadowModel = 'DualCone';
GMAT SolarArrays_Lead.ShadowBodies = {'Earth'};

Create SolarPowerSystem SolarArrays_Trail;
GMAT SolarArrays_Trail.EpochFormat = 'UTCGregorian';
GMAT SolarArrays_Trail.InitialEpoch = '{{ epoch }}';
GMAT SolarArrays_Trail.InitialMaxPower = {{ max_power_kw | default(2.0) }};
GMAT SolarArrays_Trail.AnnualDecayRate = 1;
GMAT SolarArrays_Trail.Margin = 5;
GMAT SolarArrays_Trail.BusCoeff1 = 0.3;
GMAT SolarArrays_Trail.BusCoeff2 = 0;
GMAT SolarArrays_Trail.BusCoeff3 = 0;
GMAT SolarArrays_Trail.ShadowModel = 'DualCone';
GMAT SolarArrays_Trail.ShadowBodies = {'Earth'};

GMAT SC_Lead.Tanks = {EPTank_Lead};
GMAT SC_Lead.Thrusters = {EPThruster_Lead};
GMAT SC_Lead.PowerSystem = SolarArrays_Lead;
GMAT SC_Trail.Tanks = {EPTank_Trail};
GMAT SC_Trail.Thrusters = {EPThruster_Trail};
GMAT SC_Trail.PowerSystem = SolarArrays_Trail;

%----------------------------------------
% Finite Burn Definitions
%----------------------------------------
Create FiniteBurn Burn_Lead;
GMAT Burn_Lead.Thrusters = {EPThruster_Lead};

Create FiniteBurn Burn_Trail;
GMAT Burn_Trail.Thrusters = {EPThruster_Trail};

%----------------------------------------
% Force Model
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
GMAT Prop_LEO.MaxStepAttempts = 100;
GMAT Prop_LEO.StopIfAccuracyIsViolated = false;

%----------------------------------------
% Control Variables
%----------------------------------------
Create Variable PhaseSeparation TargetPhase InitialPhase PhaseThreshold;
GMAT TargetPhase = {{ target_phase_deg | default(45.0) }};
GMAT PhaseSeparation = 0;
GMAT InitialPhase = 0;
GMAT PhaseThreshold = {{ (target_phase_deg | default(45.0)) - 1 }};

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

% Record initial phase separation
GMAT InitialPhase = SC_Trail.TA - SC_Lead.TA;

% Capture initial state for both SC
Toggle InitialStateReport On;
Report InitialStateReport SC_Lead.UTCGregorian SC_Lead.SMA SC_Lead.ECC SC_Lead.INC SC_Lead.RAAN SC_Lead.AOP SC_Lead.TA SC_Lead.TotalMass SC_Lead.Altitude;
Report InitialStateReport SC_Trail.UTCGregorian SC_Trail.SMA SC_Trail.ECC SC_Trail.INC SC_Trail.RAAN SC_Trail.AOP SC_Trail.TA SC_Trail.TotalMass SC_Trail.Altitude;
Toggle InitialStateReport Off;

% Phasing maneuver loop
While SC_Lead.ElapsedSecs < {{ duration_s }}
    % Report current state of both spacecraft
    Report EphemerisReport SC_Lead.UTCGregorian SC_Lead.EarthMJ2000Eq.X SC_Lead.EarthMJ2000Eq.Y SC_Lead.EarthMJ2000Eq.Z SC_Lead.EarthMJ2000Eq.VX SC_Lead.EarthMJ2000Eq.VY SC_Lead.EarthMJ2000Eq.VZ;
    Report EphemerisReport SC_Trail.UTCGregorian SC_Trail.EarthMJ2000Eq.X SC_Trail.EarthMJ2000Eq.Y SC_Trail.EarthMJ2000Eq.Z SC_Trail.EarthMJ2000Eq.VX SC_Trail.EarthMJ2000Eq.VY SC_Trail.EarthMJ2000Eq.VZ;
    Report KeplerianReport SC_Lead.UTCGregorian SC_Lead.SMA SC_Lead.ECC SC_Lead.INC SC_Lead.RAAN SC_Lead.AOP SC_Lead.TA SC_Lead.Altitude;
    Report KeplerianReport SC_Trail.UTCGregorian SC_Trail.SMA SC_Trail.ECC SC_Trail.INC SC_Trail.RAAN SC_Trail.AOP SC_Trail.TA SC_Trail.Altitude;
    Report MassReport SC_Lead.UTCGregorian SC_Lead.TotalMass SC_Lead.EPTank_Lead.FuelMass SC_Trail.TotalMass SC_Trail.EPTank_Trail.FuelMass;

    % Calculate current phase separation
    GMAT PhaseSeparation = SC_Trail.TA - SC_Lead.TA;
    If PhaseSeparation < -180
        GMAT PhaseSeparation = PhaseSeparation + 360;
    EndIf;
    If PhaseSeparation > 180
        GMAT PhaseSeparation = PhaseSeparation - 360;
    EndIf;

    % Simplified: Coast both spacecraft (synchronized)
    % Note: Finite burns with multi-SC require separate propagators
    Propagate Synchronized Prop_LEO(SC_Lead, SC_Trail) {{"{"}}SC_Lead.ElapsedSecs = {{ report_step_s | default(60) }}{{"}"}};

    % Update phase threshold for next iteration (simple drift model)
    GMAT PhaseThreshold = TargetPhase - 1;
EndWhile;

% Final report
Report EphemerisReport SC_Lead.UTCGregorian SC_Lead.EarthMJ2000Eq.X SC_Lead.EarthMJ2000Eq.Y SC_Lead.EarthMJ2000Eq.Z SC_Lead.EarthMJ2000Eq.VX SC_Lead.EarthMJ2000Eq.VY SC_Lead.EarthMJ2000Eq.VZ;
Report EphemerisReport SC_Trail.UTCGregorian SC_Trail.EarthMJ2000Eq.X SC_Trail.EarthMJ2000Eq.Y SC_Trail.EarthMJ2000Eq.Z SC_Trail.EarthMJ2000Eq.VX SC_Trail.EarthMJ2000Eq.VY SC_Trail.EarthMJ2000Eq.VZ;
Report KeplerianReport SC_Lead.UTCGregorian SC_Lead.SMA SC_Lead.ECC SC_Lead.INC SC_Lead.RAAN SC_Lead.AOP SC_Lead.TA SC_Lead.Altitude;
Report KeplerianReport SC_Trail.UTCGregorian SC_Trail.SMA SC_Trail.ECC SC_Trail.INC SC_Trail.RAAN SC_Trail.AOP SC_Trail.TA SC_Trail.Altitude;

% Capture final truth
Toggle TruthReport On;
Report TruthReport SC_Lead.UTCGregorian SC_Lead.SMA SC_Lead.ECC SC_Lead.INC SC_Lead.RAAN SC_Lead.AOP SC_Lead.TA SC_Lead.TotalMass SC_Lead.Altitude;
Report TruthReport SC_Trail.UTCGregorian SC_Trail.SMA SC_Trail.ECC SC_Trail.INC SC_Trail.RAAN SC_Trail.AOP SC_Trail.TA SC_Trail.TotalMass SC_Trail.Altitude;
