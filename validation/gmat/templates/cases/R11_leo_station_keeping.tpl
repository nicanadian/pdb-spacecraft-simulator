%----------------------------------------
% R11: LEO Station Keeping Regression Test
% Adapted from Ex_LEOStationKeeping.script
%
% LEO station keeping with SK maneuver capture
% - Maintains altitude corridor using impulsive burns
% - Fixed epoch: 15 Jan 2025 00:00:00.000
% - Standard reports with maneuver logging
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
% Targeting Variables
%----------------------------------------
Create Variable AltitudeMin AltitudeMax SKCounter MinRadPer;
GMAT AltitudeMin = {{ altitude_min_km | default(495) }};
GMAT AltitudeMax = {{ altitude_max_km | default(505) }};
GMAT SKCounter = 0;
GMAT MinRadPer = {{ 6378.137 + (altitude_min_km | default(495)) }};

%----------------------------------------
% Differential Corrector
%----------------------------------------
Create DifferentialCorrector DC;

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

Create ReportFile EventReport;
GMAT EventReport.Filename = '{{ output_dir }}/events_{{ case_id }}.txt';
GMAT EventReport.Precision = 16;
GMAT EventReport.WriteHeaders = true;
GMAT EventReport.LeftJustify = On;
GMAT EventReport.FixedWidth = true;
GMAT EventReport.Delimiter = ' ';
GMAT EventReport.ColumnWidth = 23;
GMAT EventReport.WriteReport = false;

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

% Main station keeping loop
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    % Report current state
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;

    % Check if altitude at perigee is below minimum
    If {{ spacecraft_name }}.RadPer < MinRadPer
        % Need to raise orbit
        GMAT SKCounter = SKCounter + 1;

        % Record maneuver event
        Toggle EventReport On;
        Report EventReport {{ spacecraft_name }}.UTCGregorian;

        % Target desired apogee altitude
        Target DC {{"{"}}SolveMode = Solve, ExitMode = SaveAndContinue{{"}"}};
            Vary DC(SKBurn.Element1 = 0.001, {{"{"}}Perturbation = 0.0001, Lower = 0, Upper = 0.1, MaxStep = 0.01{{"}"}});
            Maneuver SKBurn({{ spacecraft_name }});
            Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};
            Achieve DC({{ spacecraft_name }}.Altitude = {{ altitude_target_km | default(500) }}, {{"{"}}Tolerance = 0.1{{"}"}});
        EndTarget;

        Report EventReport {{ spacecraft_name }}.UTCGregorian;
        Toggle EventReport Off;
    EndIf;

    % Propagate one orbit or reporting step
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

% Final reports
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
