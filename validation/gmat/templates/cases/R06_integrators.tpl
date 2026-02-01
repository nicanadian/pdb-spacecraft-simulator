%----------------------------------------
% R06: Integrators Regression Test
% Adapted from Ex_Integrators.script
%
% Integrator comparison with step count capture
%----------------------------------------

%----------------------------------------
% Spacecraft Definition
%----------------------------------------
{% include 'base_spacecraft.tpl' %}

%----------------------------------------
% Multiple Propagators with Different Integrators
%----------------------------------------
Create ForceModel FM_Base;
GMAT FM_Base.CentralBody = Earth;
GMAT FM_Base.PrimaryBodies = {Earth};
GMAT FM_Base.GravityField.Earth.Degree = 4;
GMAT FM_Base.GravityField.Earth.Order = 4;
GMAT FM_Base.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT FM_Base.Drag = None;
GMAT FM_Base.SRP = Off;
GMAT FM_Base.ErrorControl = RSSStep;

Create Propagator Prop_RK89;
GMAT Prop_RK89.FM = FM_Base;
GMAT Prop_RK89.Type = RungeKutta89;
GMAT Prop_RK89.InitialStepSize = {{ initial_step_s | default(60) }};
GMAT Prop_RK89.Accuracy = {{ accuracy | default(1e-12) }};
GMAT Prop_RK89.MinStep = 0.001;
GMAT Prop_RK89.MaxStep = 2700;

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
    Propagate Prop_RK89({{ spacecraft_name }}) {{"{"}}{{ spacecraft_name }}.ElapsedSecs = {{ report_step_s }}{{"}"}};
EndWhile;

Toggle TruthReport On;
Report TruthReport {{ spacecraft_name }}.UTCGregorian {{ spacecraft_name }}.SMA {{ spacecraft_name }}.ECC {{ spacecraft_name }}.INC {{ spacecraft_name }}.RAAN {{ spacecraft_name }}.AOP {{ spacecraft_name }}.TA {{ spacecraft_name }}.TotalMass {{ spacecraft_name }}.Altitude;
