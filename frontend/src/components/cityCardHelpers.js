const COLOR_SCHEMES = [
  { primary: '#6366f1', secondary: '#818cf8' }, // Indigo
  { primary: '#8b5cf6', secondary: '#a78bfa' }, // Purple
  { primary: '#ec4899', secondary: '#f472b6' }, // Pink
  { primary: '#f59e0b', secondary: '#fbbf24' }, // Amber
  { primary: '#10b981', secondary: '#34d399' }, // Emerald
  { primary: '#06b6d4', secondary: '#22d3ee' }, // Cyan
  { primary: '#ef4444', secondary: '#f87171' }, // Red
  { primary: '#3b82f6', secondary: '#60a5fa' }, // Blue
];

function getCityTime(date, offsetHours) {
  const timestamp = date.getTime();
  const offsetMillis = offsetHours * 60 * 60 * 1000;

  return new Date(timestamp + offsetMillis);
}

export function formatCityTime(date, offsetHours, is24Hour) {
  const cityTime = getCityTime(date, offsetHours);

  return cityTime.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: !is24Hour,
    timeZone: 'UTC',
  });
}

export function formatCityDate(date, offsetHours) {
  const cityTime = getCityTime(date, offsetHours);

  return cityTime.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export function getCityColorScheme(cityName) {
  const hash = cityName.split('').reduce((accumulator, char) => {
    return accumulator + char.charCodeAt(0);
  }, 0);

  return COLOR_SCHEMES[hash % COLOR_SCHEMES.length];
}