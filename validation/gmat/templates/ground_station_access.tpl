%----------------------------------------
% Ground Station Access Validation Script
% Auto-generated for visibility computation validation
%
% Scenario: {{ scenario_name }}
% Duration: {{ duration_hours }} hours
%----------------------------------------

%----------------------------------------
% Spacecraft
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Propagator
%----------------------------------------
{% include 'propagator_config.tpl' %}

%----------------------------------------
% Ground Stations
%----------------------------------------
{% for station in ground_stations %}
Create GroundStation {{ station.id }};
GMAT {{ station.id }}.StateType = Spherical;
GMAT {{ station.id }}.HorizonReference = Ellipsoid;
GMAT {{ station.id }}.Location1 = {{ station.lat_deg }};
GMAT {{ station.id }}.Location2 = {{ station.lon_deg }};
GMAT {{ station.id }}.Location3 = {{ station.alt_km }};
GMAT {{ station.id }}.Id = '{{ station.id }}';
GMAT {{ station.id }}.MinimumElevationAngle = {{ station.min_el_deg }};
{% endfor %}

%----------------------------------------
% Contact Locators
%----------------------------------------
{% for station in ground_stations %}
Create ContactLocator {{ station.id }}Locator;
GMAT {{ station.id }}Locator.Target = {{ spacecraft_name }};
GMAT {{ station.id }}Locator.Observers = {{ '{' }}{{ station.id }}{{ '}' }};
GMAT {{ station.id }}Locator.Filename = '{{ output_dir }}/access_{{ station.id }}_{{ scenario_id }}.txt';
GMAT {{ station.id }}Locator.OccultingBodies = {Earth};
GMAT {{ station.id }}Locator.InputEpochFormat = 'UTCGregorian';
GMAT {{ station.id }}Locator.InitialEpoch = '{{ epoch }}';
GMAT {{ station.id }}Locator.StepSize = {{ locator_step_s }};
GMAT {{ station.id }}Locator.FinalEpoch = '{{ end_epoch }}';
GMAT {{ station.id }}Locator.UseLightTimeDelay = false;
GMAT {{ station.id }}Locator.UseStellarAberration = false;
GMAT {{ station.id }}Locator.WriteReport = true;
GMAT {{ station.id }}Locator.RunMode = Automatic;
GMAT {{ station.id }}Locator.UseEntireInterval = true;
GMAT {{ station.id }}Locator.LightTimeDirection = Receive;
{% endfor %}

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

{% for station in ground_stations %}
Create ReportFile {{ station.id }}ElevReport;
GMAT {{ station.id }}ElevReport.Filename = '{{ output_dir }}/elevation_{{ station.id }}_{{ scenario_id }}.txt';
GMAT {{ station.id }}ElevReport.Precision = 16;
GMAT {{ station.id }}ElevReport.WriteHeaders = true;
GMAT {{ station.id }}ElevReport.LeftJustify = On;
GMAT {{ station.id }}ElevReport.ZeroFill = Off;
GMAT {{ station.id }}ElevReport.FixedWidth = true;
GMAT {{ station.id }}ElevReport.Delimiter = ' ';
GMAT {{ station.id }}ElevReport.ColumnWidth = 23;
GMAT {{ station.id }}ElevReport.WriteReport = true;
{% endfor %}

%----------------------------------------
% Mission Sequence
%----------------------------------------
BeginMissionSequence;

% Propagate and report ephemeris
While {{ spacecraft_name }}.ElapsedSecs < {{ duration_s }}
    Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
    {% for station in ground_stations %}
    Report {{ station.id }}ElevReport {{ spacecraft_name }}.UTCGregorian {{ station.id }}.{{ spacecraft_name }}.Elevation {{ station.id }}.{{ spacecraft_name }}.Azimuth {{ station.id }}.{{ spacecraft_name }}.Range;
    {% endfor %}
    Propagate {{ propagator_name }}({{ spacecraft_name }}) {{ '{' }}{{ spacecraft_name }}.ElapsedSecs = {{ spacecraft_name }}.ElapsedSecs + {{ report_step_s }}{{ '}' }};
EndWhile;

% Final report
Report EphemerisReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.EarthMJ2000Eq.X {{ spacecraft_name }}.EarthMJ2000Eq.Y {{ spacecraft_name }}.EarthMJ2000Eq.Z {{ spacecraft_name }}.EarthMJ2000Eq.VX {{ spacecraft_name }}.EarthMJ2000Eq.VY {{ spacecraft_name }}.EarthMJ2000Eq.VZ;
{% for station in ground_stations %}
Report {{ station.id }}ElevReport {{ spacecraft_name }}.UTCGregorian {{ station.id }}.{{ spacecraft_name }}.Elevation {{ station.id }}.{{ spacecraft_name }}.Azimuth {{ station.id }}.{{ spacecraft_name }}.Range;
{% endfor %}
