%----------------------------------------
% Propagator Configuration Template
% Auto-generated for validation
%----------------------------------------

% Force Model
Create ForceModel {{ force_model_name }};
GMAT {{ force_model_name }}.CentralBody = Earth;
GMAT {{ force_model_name }}.PrimaryBodies = {Earth};
GMAT {{ force_model_name }}.PointMasses = {Luna, Sun};

{% if high_fidelity %}
% High-fidelity gravity field
GMAT {{ force_model_name }}.GravityField.Earth.Degree = 70;
GMAT {{ force_model_name }}.GravityField.Earth.Order = 70;
GMAT {{ force_model_name }}.GravityField.Earth.StmLimit = 100;
GMAT {{ force_model_name }}.GravityField.Earth.PotentialFile = 'JGM2.cof';
GMAT {{ force_model_name }}.GravityField.Earth.TideModel = 'None';

% Atmospheric drag
GMAT {{ force_model_name }}.Drag.AtmosphereModel = MSISE90;
GMAT {{ force_model_name }}.Drag.HistoricWeatherSource = 'ConstantFluxAndGeoMag';
GMAT {{ force_model_name }}.Drag.PredictedWeatherSource = 'ConstantFluxAndGeoMag';
GMAT {{ force_model_name }}.Drag.CSSISpaceWeatherFile = 'SpaceWeather-All-v1.2.txt';
GMAT {{ force_model_name }}.Drag.SchattenFile = 'SchattenPredict.txt';
GMAT {{ force_model_name }}.Drag.F107 = {{ f107 }};
GMAT {{ force_model_name }}.Drag.F107A = {{ f107a }};
GMAT {{ force_model_name }}.Drag.MagneticIndex = {{ kp }};

% Solar Radiation Pressure
GMAT {{ force_model_name }}.SRP = On;
GMAT {{ force_model_name }}.SRP.Flux = 1367.0;
GMAT {{ force_model_name }}.SRP.SRPModel = Spherical;
GMAT {{ force_model_name }}.SRP.Nominal_Sun = 149597870.691;
{% else %}
% Standard fidelity gravity (point mass)
GMAT {{ force_model_name }}.GravityField.Earth.Degree = 4;
GMAT {{ force_model_name }}.GravityField.Earth.Order = 4;
GMAT {{ force_model_name }}.GravityField.Earth.StmLimit = 100;
GMAT {{ force_model_name }}.GravityField.Earth.PotentialFile = 'JGM2.cof';

{% if include_drag %}
% Atmospheric drag (simplified)
GMAT {{ force_model_name }}.Drag.AtmosphereModel = JacchiaRoberts;
GMAT {{ force_model_name }}.Drag.F107 = {{ f107 }};
GMAT {{ force_model_name }}.Drag.F107A = {{ f107a }};
{% else %}
GMAT {{ force_model_name }}.Drag = None;
{% endif %}

GMAT {{ force_model_name }}.SRP = Off;
{% endif %}

GMAT {{ force_model_name }}.ErrorControl = RSSStep;

% Integrator
Create Propagator {{ propagator_name }};
GMAT {{ propagator_name }}.FM = {{ force_model_name }};
GMAT {{ propagator_name }}.Type = {{ integrator_type }};
GMAT {{ propagator_name }}.InitialStepSize = {{ initial_step_s }};
GMAT {{ propagator_name }}.Accuracy = {{ accuracy }};
GMAT {{ propagator_name }}.MinStep = {{ min_step_s }};
GMAT {{ propagator_name }}.MaxStep = {{ max_step_s }};
GMAT {{ propagator_name }}.MaxStepAttempts = 50;
GMAT {{ propagator_name }}.StopIfAccuracyIsViolated = true;
