%----------------------------------------
% R12: Tutorial LEO Station Keeping Regression Test
% Adapted from Tut_LEOStationKeeping.script
%
% Simplified LEO station keeping tutorial
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Chemical Thruster for SK
%----------------------------------------
Create ChemicalTank SKTank;
GMAT SKTank.AllowNegativeFuelMass = false;
GMAT SKTank.FuelMass = {{ propellant_kg | default(50.0) }};
GMAT SKTank.Pressure = 1500;
GMAT SKTank.Temperature = 20;
GMAT SKTank.RefTemperature = 20;
GMAT SKTank.Volume = 0.075;
GMAT SKTank.FuelDensity = 1260;
GMAT SKTank.PressureModel = PressureRegulated;

Create ChemicalThruster SKThruster;
GMAT SKThruster.CoordinateSystem = Local;
GMAT SKThruster.Origin = Earth;
GMAT SKThruster.Axes = VNB;
GMAT SKThruster.ThrustDirection1 = 1;
GMAT SKThruster.ThrustDirection2 = 0;
GMAT SKThruster.ThrustDirection3 = 0;
GMAT SKThruster.DutyCycle = 1.0;
GMAT SKThruster.DecrementMass = true;
GMAT SKThruster.Tank = {SKTank};
GMAT SKThruster.C1 = {{ thrust_n | default(500) }};
GMAT SKThruster.K1 = {{ isp_chemical | default(300) }};

GMAT {{ spacecraft_name }}.Tanks = {SKTank};
GMAT {{ spacecraft_name }}.Thrusters = {SKThruster};

%----------------------------------------
% Impulsive Burn for SK
%----------------------------------------
Create ImpulsiveBurn SKBurn;
GMAT SKBurn.CoordinateSystem = Local;
GMAT SKBurn.Origin = Earth;
GMAT SKBurn.Axes = VNB;
GMAT SKBurn.Element1 = 0;
GMAT SKBurn.Element2 = 0;
GMAT SKBurn.Element3 = 0;
GMAT SKBurn.DecrementMass = true;
GMAT SKBurn.Isp = {{ isp_chemical | default(300) }};
GMAT SKBurn.GravitationalAccel = 9.81;
GMAT SKBurn.Tank = {SKTank};

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Variables
%----------------------------------------
Create Variable AltitudeMin MinRadPer;
GMAT AltitudeMin = {{ altitude_min_km | default(495) }};
GMAT MinRadPer = {{ 6378.137 + (altitude_min_km | default(495)) }};

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

Toggle InitialStateReport On;
Report InitialStateReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
Toggle InitialStateReport Off;

While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;

    If {{ spacecraft_name }}.RadPer < MinRadPer
        Target DC {{"{"}}SolveMode = Solve, ExitMode = SaveAndContinue{{"}"}};
            Vary DC(SKBurn.Element1 = 0.001, {{"{"}}Perturbation = 0.0001, Lower = 0, Upper = 0.1, MaxStep = 0.01{{"}"}});
            Maneuver SKBurn({{ spacecraft_name }});
            Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};
            Achieve DC({{ spacecraft_name }}.Altitude = {{ altitude_target_km | default(500) }}, {{"{"}}Tolerance = 0.1{{"}"}});
        EndTarget;
    EndIf;

    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
