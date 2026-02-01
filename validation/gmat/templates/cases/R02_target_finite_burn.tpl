%----------------------------------------
% R02: Target Finite Burn Regression Test
% Adapted from Ex_TargetFiniteBurn.script
%
% Targeted finite burn using differential corrector
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports
% - Captures solver convergence
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Chemical Thruster Setup
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

Create ChemicalThruster Thruster1;
GMAT Thruster1.CoordinateSystem = Local;
GMAT Thruster1.Origin = Earth;
GMAT Thruster1.Axes = VNB;
GMAT Thruster1.ThrustDirection1 = 1;
GMAT Thruster1.ThrustDirection2 = 0;
GMAT Thruster1.ThrustDirection3 = 0;
GMAT Thruster1.DutyCycle = 1.0;
GMAT Thruster1.DecrementMass = true;
GMAT Thruster1.Tank = {FuelTank};
GMAT Thruster1.C1 = {{ thrust_n | default(500) }};
GMAT Thruster1.K1 = {{ isp_chemical | default(300) }};

GMAT {{ spacecraft_name }}.Tanks = {FuelTank};
GMAT {{ spacecraft_name }}.Thrusters = {Thruster1};

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn TargetBurn;
GMAT TargetBurn.Thrusters = {Thruster1};

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Targeting Variables
%----------------------------------------
Create Variable BurnDuration TargetAltitude;
GMAT BurnDuration = {{ initial_burn_duration_s | default(30) }};
GMAT TargetAltitude = {{ target_altitude_km | default(550) }};

%----------------------------------------
% Differential Corrector
%----------------------------------------
Create DifferentialCorrector DC;

%----------------------------------------
% Output Reports
%----------------------------------------
{% include 'includes/standard_report.tpl' %}
{% include 'includes/truth_checkpoints.tpl' %}

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Capture initial state
Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

% Target desired apogee altitude
Target DC {{"{"}}SolveMode = Solve, ExitMode = SaveAndContinue{{"}"}};
    Vary DC(BurnDuration = 30, {{"{"}}Perturbation = 0.1, Lower = 1, Upper = 120, MaxStep = 10{{"}"}});

    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Periapsis{{"}"}};

    BeginFiniteBurn TargetBurn({{ spacecraft_name }});
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = BurnDuration{{"}"}};
    EndFiniteBurn TargetBurn({{ spacecraft_name }});

    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};
    Achieve DC({{ spacecraft_name }}.Altitude = TargetAltitude, {{"{"}}Tolerance = 0.1{{"}"}});
EndTarget;

% Report post-burn state
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Propagate to end
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

% Capture final truth
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
