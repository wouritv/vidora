export const DAYS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];

export const MONTHS = [
    'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

export const TIMEZONES = [
    { value: 'Pacific/Midway', label: '(GMT-11:00) Midway' },
    { value: 'Pacific/Honolulu', label: '(GMT-10:00) Honolulu' },
    { value: 'America/Anchorage', label: '(GMT-09:00) Alaska' },
    { value: 'America/Los_Angeles', label: '(GMT-08:00) Los Ángeles' },
    { value: 'America/Denver', label: '(GMT-07:00) Denver' },
    { value: 'America/Mexico_City', label: '(GMT-06:00) Ciudad de México' },
    { value: 'America/Chicago', label: '(GMT-06:00) Chicago' },
    { value: 'America/New_York', label: '(GMT-05:00) Nueva York' },
    { value: 'America/Bogota', label: '(GMT-05:00) Bogotá' },
    { value: 'America/Caracas', label: '(GMT-04:00) Caracas' },
    { value: 'America/Santiago', label: '(GMT-04:00) Santiago' },
    { value: 'America/Argentina/Buenos_Aires', label: '(GMT-03:00) Buenos Aires' },
    { value: 'America/Sao_Paulo', label: '(GMT-03:00) São Paulo' },
    { value: 'Atlantic/Azores', label: '(GMT-01:00) Azores' },
    { value: 'UTC', label: '(GMT+00:00) UTC' },
    { value: 'Europe/London', label: '(GMT+00:00) Londres' },
    { value: 'Europe/Madrid', label: '(GMT+01:00) Madrid' },
    { value: 'Europe/Paris', label: '(GMT+01:00) París' },
    { value: 'Europe/Berlin', label: '(GMT+01:00) Berlín' },
    { value: 'Europe/Rome', label: '(GMT+01:00) Roma' },
    { value: 'Africa/Lagos', label: '(GMT+01:00) Lagos' },
    { value: 'Europe/Istanbul', label: '(GMT+03:00) Estambul' },
    { value: 'Asia/Dubai', label: '(GMT+04:00) Dubái' },
    { value: 'Asia/Kolkata', label: '(GMT+05:30) India' },
    { value: 'Asia/Bangkok', label: '(GMT+07:00) Bangkok' },
    { value: 'Asia/Shanghai', label: '(GMT+08:00) Shanghái' },
    { value: 'Asia/Tokyo', label: '(GMT+09:00) Tokio' },
    { value: 'Australia/Sydney', label: '(GMT+10:00) Sídney' },
    { value: 'Pacific/Auckland', label: '(GMT+12:00) Auckland' },
];

/**
 * Human-friendly day label relative to today: "Hoy", "Mañana", or weekday name.
 * @param {Date} date
 * @returns {string}
 */
export function getDayLabel(date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const target = new Date(date);
    target.setHours(0, 0, 0, 0);

    if (target.getTime() === today.getTime()) return 'Hoy';
    if (target.getTime() === tomorrow.getTime()) return 'Mañana';
    return DAYS[target.getDay()];
}

/**
 * Format a date as "D Mon" (e.g. "14 Jul").
 * @param {Date} date
 * @returns {string}
 */
export function formatDate(date) {
    return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

/**
 * Detect the browser timezone, falling back to "UTC" if not in the TIMEZONES list.
 * @returns {string} IANA timezone identifier
 */
export function detectTimezone() {
    try {
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (TIMEZONES.some((t) => t.value === tz)) return tz;
        return 'UTC';
    } catch {
        return 'UTC';
    }
}

