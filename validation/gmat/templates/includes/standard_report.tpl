%----------------------------------------
% Standard Regression Output Reports
% Include this template to add standardized output files
%----------------------------------------

%----------------------------------------
% Ephemeris Report (ECI Cartesian)
%----------------------------------------
Create ReportFile EphemerisReport;
GMAT EphemerisReport.SolverIterations = Current;
GMAT EphemerisReport.UpperLeft = [0 0];
GMAT EphemerisReport.Size = [0 0];
GMAT EphemerisReport.RelativeZOrder = 0;
GMAT EphemerisReport.Maximized = false;
GMAT EphemerisReport.Filename = '{{ output_dir }}/ephemeris_{{ case_id }}.txt';
GMAT EphemerisReport.Precision = 16;
GMAT EphemerisReport.WriteHeaders = true;
GMAT EphemerisReport.LeftJustify = On;
GMAT EphemerisReport.ZeroFill = Off;
GMAT EphemerisReport.FixedWidth = true;
GMAT EphemerisReport.Delimiter = ' ';
GMAT EphemerisReport.ColumnWidth = 23;
GMAT EphemerisReport.WriteReport = true;

%----------------------------------------
% Keplerian Report (Orbital Elements)
%----------------------------------------
Create ReportFile KeplerianReport;
GMAT KeplerianReport.SolverIterations = Current;
GMAT KeplerianReport.UpperLeft = [0 0];
GMAT KeplerianReport.Size = [0 0];
GMAT KeplerianReport.RelativeZOrder = 0;
GMAT KeplerianReport.Maximized = false;
GMAT KeplerianReport.Filename = '{{ output_dir }}/keplerian_{{ case_id }}.txt';
GMAT KeplerianReport.Precision = 16;
GMAT KeplerianReport.WriteHeaders = true;
GMAT KeplerianReport.LeftJustify = On;
GMAT KeplerianReport.ZeroFill = Off;
GMAT KeplerianReport.FixedWidth = true;
GMAT KeplerianReport.Delimiter = ' ';
GMAT KeplerianReport.ColumnWidth = 23;
GMAT KeplerianReport.WriteReport = true;

%----------------------------------------
% Mass Report (Propellant Tracking)
%----------------------------------------
Create ReportFile MassReport;
GMAT MassReport.SolverIterations = Current;
GMAT MassReport.UpperLeft = [0 0];
GMAT MassReport.Size = [0 0];
GMAT MassReport.RelativeZOrder = 0;
GMAT MassReport.Maximized = false;
GMAT MassReport.Filename = '{{ output_dir }}/mass_{{ case_id }}.txt';
GMAT MassReport.Precision = 16;
GMAT MassReport.WriteHeaders = true;
GMAT MassReport.LeftJustify = On;
GMAT MassReport.ZeroFill = Off;
GMAT MassReport.FixedWidth = true;
GMAT MassReport.Delimiter = ' ';
GMAT MassReport.ColumnWidth = 23;
GMAT MassReport.WriteReport = true;

{% if has_events %}
%----------------------------------------
% Event Report (Maneuvers, Eclipse, etc.)
%----------------------------------------
Create ReportFile EventReport;
GMAT EventReport.SolverIterations = Current;
GMAT EventReport.Filename = '{{ output_dir }}/events_{{ case_id }}.txt';
GMAT EventReport.Precision = 16;
GMAT EventReport.WriteHeaders = true;
GMAT EventReport.LeftJustify = On;
GMAT EventReport.ZeroFill = Off;
GMAT EventReport.FixedWidth = true;
GMAT EventReport.Delimiter = ' ';
GMAT EventReport.ColumnWidth = 23;
GMAT EventReport.WriteReport = false;
{% endif %}

%----------------------------------------
% Standard Report Macros
% Use these in mission sequence to report state
%----------------------------------------
% Report ephemeris:
%   Report EphemerisReport {{ sc_name }}.UTCGregorian {{ sc_name }}.EarthMJ2000Eq.X {{ sc_name }}.EarthMJ2000Eq.Y {{ sc_name }}.EarthMJ2000Eq.Z {{ sc_name }}.EarthMJ2000Eq.VX {{ sc_name }}.EarthMJ2000Eq.VY {{ sc_name }}.EarthMJ2000Eq.VZ;
%
% Report keplerian:
%   Report KeplerianReport {{ sc_name }}.UTCGregorian {{ sc_name }}.SMA {{ sc_name }}.ECC {{ sc_name }}.INC {{ sc_name }}.RAAN {{ sc_name }}.AOP {{ sc_name }}.TA {{ sc_name }}.Altitude;
%
% Report mass:
%   Report MassReport {{ sc_name }}.UTCGregorian {{ sc_name }}.TotalMass {{ sc_name }}.ChemFuelMass;
