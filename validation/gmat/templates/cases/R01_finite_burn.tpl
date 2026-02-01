%----------------------------------------
% R01: Finite Burn Regression Test
% Adapted from Ex_FiniteBurn.script
%
% Basic finite burn maneuver with chemical thruster
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports
% - Truth checkpoint at end
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
GMAT Thruster1.ThrustScaleFactor = 1.0;
GMAT Thruster1.DecrementMass = true;
GMAT Thruster1.Tank = {FuelTank};
GMAT Thruster1.MixRatio = [1];
GMAT Thruster1.GravitationalAccel = 9.81;
GMAT Thruster1.C1 = {{ thrust_n | default(500) }};
GMAT Thruster1.C2 = 0;
GMAT Thruster1.C3 = 0;
GMAT Thruster1.C4 = 0;
GMAT Thruster1.C5 = 0;
GMAT Thruster1.C6 = 0;
GMAT Thruster1.C7 = 0;
GMAT Thruster1.C8 = 0;
GMAT Thruster1.C9 = 0;
GMAT Thruster1.C10 = 0;
GMAT Thruster1.C11 = 0;
GMAT Thruster1.C12 = 0;
GMAT Thruster1.C13 = 0;
GMAT Thruster1.C14 = 0;
GMAT Thruster1.C15 = 0;
GMAT Thruster1.C16 = 0;
GMAT Thruster1.K1 = {{ isp_chemical | default(300) }};
GMAT Thruster1.K2 = 0;
GMAT Thruster1.K3 = 0;
GMAT Thruster1.K4 = 0;
GMAT Thruster1.K5 = 0;
GMAT Thruster1.K6 = 0;
GMAT Thruster1.K7 = 0;
GMAT Thruster1.K8 = 0;
GMAT Thruster1.K9 = 0;
GMAT Thruster1.K10 = 0;
GMAT Thruster1.K11 = 0;
GMAT Thruster1.K12 = 0;
GMAT Thruster1.K13 = 0;
GMAT Thruster1.K14 = 0;
GMAT Thruster1.K15 = 0;
GMAT Thruster1.K16 = 0;

GMAT {{ spacecraft_name }}.Tanks = {FuelTank};
GMAT {{ spacecraft_name }}.Thrusters = {Thruster1};

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn FiniteBurn1;
GMAT FiniteBurn1.Thrusters = {Thruster1};
GMAT FiniteBurn1.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Standard Reports
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
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Toggle InitialStateReport Off;

% Propagate to apogee
Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};

% Report state before burn
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Record burn start event
Toggle EventReport On;
Report EventReport {{ spacecraft_name }}.UTCGregorian;

% Execute finite burn ({{ burn_duration_s | default(60) }} seconds)
BeginFiniteBurn FiniteBurn1({{ spacecraft_name }});
Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ burn_duration_s | default(60) }}{{"}"}};
EndFiniteBurn FiniteBurn1({{ spacecraft_name }});

% Record burn end event
Report EventReport {{ spacecraft_name }}.UTCGregorian;
Toggle EventReport Off;

% Report state after burn
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;

% Propagate to end of scenario
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.FuelTank.FuelMass;
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}, OrbitColor = Red{{"}"}};
EndWhile;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
