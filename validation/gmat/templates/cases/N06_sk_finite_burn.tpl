%----------------------------------------
% N06: Station Keeping Finite Burn Conversion
% NEW OPS-GRADE REFERENCE SCENARIO
%
% Convert impulsive SK to finite burn (same corridor as R11)
% - Uses finite burns instead of impulsive burns
% - Duration-based targeting
% - 7-day simulation
%
% Acceptance criteria:
% - Same corridor performance as impulsive
% - Burns expressed as Begin/EndFiniteBurn
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Chemical Thruster for SK (Finite Burns)
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
GMAT SKThruster.ThrustDirection1 = 1;   % Prograde
GMAT SKThruster.ThrustDirection2 = 0;
GMAT SKThruster.ThrustDirection3 = 0;
GMAT SKThruster.DutyCycle = 1.0;
GMAT SKThruster.ThrustScaleFactor = 1.0;
GMAT SKThruster.DecrementMass = true;
GMAT SKThruster.Tank = {SKTank};
GMAT SKThruster.MixRatio = [1];
GMAT SKThruster.GravitationalAccel = 9.81;
GMAT SKThruster.C1 = {{ thrust_n | default(500) }};
GMAT SKThruster.K1 = {{ isp_chemical | default(300) }};

GMAT {{ spacecraft_name }}.Tanks = {SKTank};
GMAT {{ spacecraft_name }}.Thrusters = {SKThruster};

%----------------------------------------
% Finite Burn Definition (replaces ImpulsiveBurn)
%----------------------------------------
Create FiniteBurn SKFiniteBurn;
GMAT SKFiniteBurn.Thrusters = {SKThruster};
GMAT SKFiniteBurn.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

%----------------------------------------
% Propagator Configuration
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Targeting Variables
%----------------------------------------
Create Variable AltitudeMin AltitudeMax AltitudeTarget;
Create Variable BurnDuration SKCounter MinRadPer;
GMAT AltitudeMin = {{ altitude_min_km | default(495) }};
GMAT AltitudeMax = {{ altitude_max_km | default(505) }};
GMAT AltitudeTarget = {{ altitude_target_km | default(500) }};
GMAT BurnDuration = {{ initial_burn_duration_s | default(5.0) }};
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

% Main station keeping loop with finite burns
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    % Report current state
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
    Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;

    % Check if altitude at perigee is below minimum (need to raise)
    If {{ spacecraft_name }}.RadPer < MinRadPer
        % Propagate to apogee for optimal prograde burn
        Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};

        GMAT SKCounter = SKCounter + 1;

        % Record burn start
        Toggle EventReport On;
        Report EventReport {{ spacecraft_name }}.UTCGregorian;

        % Target desired apogee altitude using finite burn duration
        Target DC {{"{"}}SolveMode = Solve, ExitMode = SaveAndContinue{{"}"}};
            Vary DC(BurnDuration = 5, {{"{"}}Perturbation = 0.1, Lower = 0.1, Upper = 60, MaxStep = 5{{"}"}});

            BeginFiniteBurn SKFiniteBurn({{ spacecraft_name }});
            Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = BurnDuration{{"}"}};
            EndFiniteBurn SKFiniteBurn({{ spacecraft_name }});

            Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.Apoapsis{{"}"}};
            Achieve DC({{ spacecraft_name }}.Altitude = AltitudeTarget, {{"{"}}Tolerance = 0.1{{"}"}});
        EndTarget;

        % Record burn end
        Report EventReport {{ spacecraft_name }}.UTCGregorian;
        Toggle EventReport Off;

        Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
        Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
        Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;
    EndIf;

    % Propagate one reporting step
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s | default(60) }}{{"}"}};
EndWhile;

% Final reports
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report KeplerianReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.Altitude;
Report MassReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.SKTank.FuelMass;

% Capture final truth checkpoint
Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
