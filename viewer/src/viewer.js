/**
 * Cesium viewer setup and configuration.
 */
import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';

/**
 * Initialize the Cesium viewer with appropriate settings.
 *
 * @param {string} containerId - DOM element ID for the viewer
 * @returns {Promise<Cesium.Viewer>} Initialized viewer
 */
export async function initViewer(containerId) {
    // Disable Ion - empty string like gravitys-travail
    Cesium.Ion.defaultAccessToken = '';

    // Create viewer with no base imagery first
    const viewer = new Cesium.Viewer(containerId, {
        baseLayerPicker: false,
        imageryProvider: false,  // Start with no imagery
        geocoder: false,
        homeButton: true,
        sceneModePicker: true,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: true,
        vrButton: false,
        shadows: false,
        shouldAnimate: false,
        skyBox: false,  // Key: disable skyBox like gravitys-travail
        infoBox: false,
        selectionIndicator: false,
    });

    // Configure scene
    const scene = viewer.scene;
    scene.backgroundColor = Cesium.Color.fromCssColorString('#111122');

    // Ensure globe is visible and properly configured
    if (scene.globe) {
        scene.globe.show = true;
        scene.globe.enableLighting = false;  // Disable lighting so globe is always visible
        scene.globe.showGroundAtmosphere = false;
        scene.globe.baseColor = Cesium.Color.fromCssColorString('#1a1a3e'); // Visible base color
    }

    if (scene.skyAtmosphere) {
        scene.skyAtmosphere.show = false;
    }

    if (scene.fog) {
        scene.fog.enabled = false;
    }

    scene.highDynamicRange = false;

    // Add NaturalEarthII imagery AFTER viewer is created
    // This is the pattern that works more reliably
    try {
        const naturalEarthUrl = Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII');
        console.log('Loading NaturalEarthII from:', naturalEarthUrl);

        const imageryProvider = await Cesium.TileMapServiceImageryProvider.fromUrl(naturalEarthUrl);
        viewer.imageryLayers.addImageryProvider(imageryProvider);
        console.log('NaturalEarthII imagery layer added successfully');
    } catch (error) {
        console.error('Failed to load NaturalEarthII imagery:', error);
    }

    // Set initial camera - view looking at Earth from space (20,000 km range)
    viewer.camera.lookAt(
        Cesium.Cartesian3.ZERO,
        new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-90), 20000000)
    );

    // Unlock camera so user can interact
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);

    // Don't auto-animate - user controls playback
    viewer.clock.shouldAnimate = false;

    return viewer;
}

/**
 * Load CZML data into the viewer.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {string} czmlUrl - URL to CZML file
 * @returns {Promise<Cesium.CzmlDataSource>} Loaded data source
 */
export async function loadCZML(viewer, czmlUrl) {
    console.log('Loading CZML:', czmlUrl);

    const dataSource = await Cesium.CzmlDataSource.load(czmlUrl);
    await viewer.dataSources.add(dataSource);

    // Don't touch camera - it's locked by preRender handler

    const satellite = dataSource.entities.getById('satellite_1');
    if (satellite) {
        console.log('Satellite entity loaded:', satellite.id);
    }

    return dataSource;
}

/**
 * Set the viewer time to a specific moment.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {Date|string} time - Time to set
 */
export function setViewerTime(viewer, time) {
    if (typeof time === 'string') {
        time = Cesium.JulianDate.fromIso8601(time);
    } else if (time instanceof Date) {
        time = Cesium.JulianDate.fromDate(time);
    }

    viewer.clock.currentTime = time;
}

/**
 * Configure the viewer clock for animation.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {string} startTime - ISO start time
 * @param {string} endTime - ISO end time
 * @param {number} multiplier - Time multiplier
 */
export function configureClockRange(viewer, startTime, endTime, multiplier = 60) {
    const start = Cesium.JulianDate.fromIso8601(startTime);
    const end = Cesium.JulianDate.fromIso8601(endTime);

    viewer.clock.startTime = start;
    viewer.clock.stopTime = end;
    viewer.clock.currentTime = start.clone();
    viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP;
    viewer.clock.multiplier = multiplier;
}

/**
 * Focus the camera on an entity.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {string} entityId - Entity ID to focus on
 */
export function focusOnEntity(viewer, entityId) {
    const entity = viewer.entities.getById(entityId);
    if (entity) {
        viewer.trackedEntity = entity;
    } else {
        // Try data sources
        for (const ds of viewer.dataSources.getAll()) {
            const entity = ds.entities.getById(entityId);
            if (entity) {
                viewer.trackedEntity = entity;
                break;
            }
        }
    }
}
