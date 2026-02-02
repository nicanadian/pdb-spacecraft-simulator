/**
 * Events panel for displaying simulation events.
 */
import { jumpToTime } from '../controls/timeline.js';

/**
 * Set up the events panel.
 *
 * @param {Cesium.Viewer} viewer - The viewer instance
 * @param {Object} runData - Loaded run data
 */
export function setupEventPanel(viewer, runData) {
    const eventList = document.getElementById('eventList');
    const eventCount = document.getElementById('eventCount');
    const contactList = document.getElementById('contactList');
    const contactCount = document.getElementById('contactCount');

    // Populate events
    if (runData.events && runData.events.length > 0) {
        eventCount.textContent = runData.events.length;
        renderEvents(eventList, runData.events, viewer);
    } else {
        eventCount.textContent = '0';
        eventList.innerHTML = '<li class="event-item">No events</li>';
    }

    // Populate contacts
    const allContacts = getAllContactsList(runData.contacts);
    if (allContacts.length > 0) {
        contactCount.textContent = allContacts.length;
        renderContacts(contactList, allContacts, viewer);
    } else {
        contactCount.textContent = '0';
        contactList.innerHTML = '<li class="event-item">No contacts</li>';
    }
}

/**
 * Render events to the list.
 *
 * @param {HTMLElement} container - Container element
 * @param {Array} events - Events to render
 * @param {Cesium.Viewer} viewer - The viewer
 */
function renderEvents(container, events, viewer) {
    container.innerHTML = '';

    for (const event of events) {
        const li = document.createElement('li');
        li.className = `event-item ${event.type || 'info'}`;

        const time = new Date(event.timestamp);
        const timeStr = time.toISOString().slice(11, 19);

        li.innerHTML = `
            <div class="event-time">${timeStr}</div>
            <div class="event-title">${event.title || event.message || 'Event'}</div>
        `;

        // Click to jump to time
        li.addEventListener('click', () => {
            jumpToTime(viewer, event.timestamp);
        });

        container.appendChild(li);
    }
}

/**
 * Render contacts to the list.
 *
 * @param {HTMLElement} container - Container element
 * @param {Array} contacts - Contacts to render
 * @param {Cesium.Viewer} viewer - The viewer
 */
function renderContacts(container, contacts, viewer) {
    container.innerHTML = '';

    for (const contact of contacts) {
        const li = document.createElement('li');
        li.className = 'event-item info';

        const startTime = new Date(contact.start_time);
        const timeStr = startTime.toISOString().slice(11, 19);
        const duration = contact.duration_s ? (contact.duration_s / 60).toFixed(1) : '--';

        li.innerHTML = `
            <div class="event-time">${timeStr}</div>
            <div class="event-title">${contact.station_id} (${duration} min)</div>
        `;

        // Click to jump to AOS
        li.addEventListener('click', () => {
            jumpToTime(viewer, contact.start_time);
        });

        container.appendChild(li);
    }
}

/**
 * Get all contacts as a flat sorted list.
 *
 * @param {Object} contactsData - Contacts by station
 * @returns {Array} Flat list of contacts
 */
function getAllContactsList(contactsData) {
    const contacts = [];

    for (const [stationId, windows] of Object.entries(contactsData || {})) {
        for (const window of windows) {
            contacts.push({
                ...window,
                station_id: stationId,
            });
        }
    }

    // Sort by start time
    contacts.sort((a, b) =>
        new Date(a.start_time) - new Date(b.start_time)
    );

    return contacts;
}

/**
 * Highlight an event in the list.
 *
 * @param {string} eventId - Event ID to highlight
 */
export function highlightEvent(eventId) {
    // Remove existing highlights
    document.querySelectorAll('.event-item.highlighted').forEach(el => {
        el.classList.remove('highlighted');
    });

    // Add highlight to matching event
    const eventEl = document.querySelector(`[data-event-id="${eventId}"]`);
    if (eventEl) {
        eventEl.classList.add('highlighted');
        eventEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}
