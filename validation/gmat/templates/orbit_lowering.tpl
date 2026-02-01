%----------------------------------------
% Orbit Lowering Validation Script
% Auto-generated for EP thrust modeling validation
%
% Scenario: {{ scenario_name }}
% Start Altitude: {{ start_altitude_km }} km
% Target Altitude: {{ target_altitude_km }} km
% Duration: {{ duration_hours }} hours
%----------------------------------------

%----------------------------------------
% Spacecraft with EP Thruster
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Propagator
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Finite Burn Definition
%----------------------------------------
Create FiniteBurn EPBurn;
GMAT EPBurn.Thrusters = {EPThruster1};
GMAT EPBurn.ThrottleLogicAlgorithm = 'MaxNumberOfThrusters';

%----------------------------------------
% Output Reports
%----------------------------------------
Create ReportFile EphemerisReport;
GMAT EphemerisReport.Filename = '{{ output_dir }}/ephemeris_{{ scenario_id }}.txt';
GMAT EphemerisReport.Precision = 16;
GMAT EphemerisReport.WriteHeaders = true;
GMAT EphemerisReport.LeftJustify = On;
GMAT EphemerisReport.ZeroFill = Off;
GMAT EphemerisReport.FixedWidth = true;
GMAT EphemerisReport.Delimiter = ' ';
GMAT EphemerisReport.ColumnWidth = 23;
GMAT EphemerisReport.WriteReport = true;

Create ReportFile ThrustReport;
GMAT ThrustReport.Filename = '{{ output_dir }}/thrust_{{ scenario_id }}.txt';
GMAT ThrustReport.Precision = 16;
GMAT ThrustReport.WriteHeaders = true;
GMAT ThrustReport.LeftJustify = On;
GMAT ThrustReport.ZeroFill = Off;
GMAT ThrustReport.FixedWidth = true;
GMAT ThrustReport.Delimiter = ' ';
GMAT ThrustReport.ColumnWidth = 23;
GMAT ThrustReport.WriteReport = true;

Create ReportFile PropellantReport;
GMAT PropellantReport.Filename = '{{ output_dir }}/propellant_{{ scenario_id }}.txt';
GMAT PropellantReport.Precision = 16;
GMAT PropellantReport.WriteHeaders = true;
GMAT PropellantReport.LeftJustify = On;
GMAT PropellantReport.ZeroFill = Off;
GMAT PropellantReport.FixedWidth = true;
GMAT PropellantReport.Delimiter = ' ';
GMAT PropellantReport.ColumnWidth = 23;
GMAT PropellantReport.WriteReport = true;

%----------------------------------------
% Variables
%----------------------------------------
Create Variable thrustArcStart thrustArcDuration orbitNum arcNum;
Create Variable thrustPerOrbit arcSpacing currentTA targetTA;

GMAT thrustPerOrbit = {{ thrusts_per_orbit }};
GMAT arcSpacing = 360 / thrustPerOrbit;
GMAT thrustArcDuration = {{ thrust_arc_s }};

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Initialize
GMAT orbitNum = 0;

% Main propagation loop with thrust arcs
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}

    % Report before thrust arc
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    Report PropellantReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EPTank1.FuelMass {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Earth.Altitude;

    {% for arc in thrust_arcs %}
    % Thrust Arc {{ arc.arc_id }}
    If {{ spacecraft_name }}.ElapsedSecs >= {{ arc.start_elapsed_s }} & {{ spacecraft_name }}.ElapsedSecs < {{ arc.end_elapsed_s }}
        BeginFiniteBurn EPBurn({{ spacecraft_name }});
        Report ThrustReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.Earth.TA 1.0 {{ spacecraft_name }}.EPTank1.FuelMass;
        Propagate {{ propagator_name }}({{ spacecraft_name }}) {{ '{' }}{{ spacecraft_name }}.ElapsedSecs = {{ arc.end_elapsed_s }}{{ '}' }};
        EndFiniteBurn EPBurn({{ spacecraft_name }});
        Report ThrustReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.Earth.TA 0.0 {{ spacecraft_name }}.EPTank1.FuelMass;
    EndIf;
    {% endfor %}

    % Coast propagation
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{ '{' }}{{ spacecraft_name }}.ElapsedSecs = {{ spacecraft_name }}.ElapsedSecs + {{ report_step_s }}{{ '}' }};

EndWhile;

% Final reports
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
Report PropellantReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EPTank1.FuelMass {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Earth.Altitude;
