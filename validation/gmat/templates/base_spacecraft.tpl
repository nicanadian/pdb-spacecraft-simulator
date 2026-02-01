%----------------------------------------
% Spacecraft Definition Template
% Auto-generated for validation - {{ scenario_name }}
%----------------------------------------

Create Spacecraft {{ spacecraft_name }};
GMAT {{ spacecraft_name }}.DateFormat = UTCGregorian;
GMAT {{ spacecraft_name }}.Epoch = '{{ epoch }}';
GMAT {{ spacecraft_name }}.CoordinateSystem = EarthMJ2000Eq;
GMAT {{ spacecraft_name }}.DisplayStateType = Keplerian;

% Orbital Elements
GMAT {{ spacecraft_name }}.SMA = {{ sma_km }};
GMAT {{ spacecraft_name }}.ECC = {{ ecc }};
GMAT {{ spacecraft_name }}.INC = {{ inc_deg }};
GMAT {{ spacecraft_name }}.RAAN = {{ raan_deg }};
GMAT {{ spacecraft_name }}.AOP = {{ aop_deg }};
GMAT {{ spacecraft_name }}.TA = {{ ta_deg }};

% Physical Properties
GMAT {{ spacecraft_name }}.DryMass = {{ dry_mass_kg }};
GMAT {{ spacecraft_name }}.Cd = 2.2;
GMAT {{ spacecraft_name }}.Cr = 1.8;
GMAT {{ spacecraft_name }}.DragArea = {{ drag_area_m2 }};
GMAT {{ spacecraft_name }}.SRPArea = {{ srp_area_m2 }};

{% if has_ep_thruster %}
% Electric Propulsion Tank and Thruster
Create ElectricTank EPTank1;
GMAT EPTank1.AllowNegativeFuelMass = false;
GMAT EPTank1.FuelMass = {{ propellant_kg }};

Create ElectricThruster EPThruster1;
GMAT EPThruster1.CoordinateSystem = Local;
GMAT EPThruster1.Origin = Earth;
GMAT EPThruster1.Axes = VNB;
GMAT EPThruster1.ThrustDirection1 = {{ thrust_dir_1 }};
GMAT EPThruster1.ThrustDirection2 = {{ thrust_dir_2 }};
GMAT EPThruster1.ThrustDirection3 = {{ thrust_dir_3 }};
GMAT EPThruster1.DutyCycle = 1.0;
GMAT EPThruster1.ThrustScaleFactor = 1.0;
GMAT EPThruster1.DecrementMass = true;
GMAT EPThruster1.Tank = {EPTank1};
GMAT EPThruster1.MixRatio = [1];
GMAT EPThruster1.GravitationalAccel = 9.81;
GMAT EPThruster1.ThrustModel = ConstantThrustAndIsp;
GMAT EPThruster1.MaximumUsablePower = {{ max_power_kw }};
GMAT EPThruster1.MinimumUsablePower = 0.001;
GMAT EPThruster1.ThrustCoeff1 = {{ thrust_mN }};
GMAT EPThruster1.ThrustCoeff2 = 0.0;
GMAT EPThruster1.ThrustCoeff3 = 0.0;
GMAT EPThruster1.ThrustCoeff4 = 0.0;
GMAT EPThruster1.ThrustCoeff5 = 0.0;
GMAT EPThruster1.MassFlowCoeff1 = {{ mass_flow_coeff }};
GMAT EPThruster1.MassFlowCoeff2 = 0.0;
GMAT EPThruster1.MassFlowCoeff3 = 0.0;
GMAT EPThruster1.MassFlowCoeff4 = 0.0;
GMAT EPThruster1.MassFlowCoeff5 = 0.0;
GMAT EPThruster1.Isp = {{ isp_s }};

GMAT {{ spacecraft_name }}.Tanks = {EPTank1};
GMAT {{ spacecraft_name }}.Thrusters = {EPThruster1};
{% endif %}
