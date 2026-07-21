import { useEffect, useState } from 'react';
import ClockOrbit from './ClockOrbit';
import { formatCityDate, formatCityTime, getCityColorScheme } from './cityCardHelpers';
import './CityCard.css';

function CityCard({ city, is24Hour, animationDelay }) {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
  // Update to current time every second
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const colorScheme = getCityColorScheme(city.city);

  return (
    <div 
      className={`city-card ${city.is_day ? 'day' : 'night'}`}
      style={{
        '--primary-color': colorScheme.primary,
        '--secondary-color': colorScheme.secondary,
        animationDelay: `${animationDelay}s`
      }}
    >
      <div className="city-card-header">
        <h3 className="city-name">{city.city}</h3>
        <span className={`day-night-indicator ${city.is_day ? 'day' : 'night'}`}>
          {city.is_day ? '☀️' : '🌙'}
        </span>
      </div>

      <ClockOrbit time={currentTime} colorScheme={colorScheme} />

      <div className="city-info">
        <div className="time-display">
          {formatCityTime(currentTime, city.offset_hours, is24Hour)}
        </div>
        <div className="date-display">
          {formatCityDate(currentTime, city.offset_hours)}
        </div>
        <div className="timezone-info">
          <span className="timezone-offset">UTC {city.offset_hours >= 0 ? '+' : ''}{city.offset_hours}</span>
          {city.is_dst && <span className="dst-indicator">DST</span>}
        </div>
      </div>
    </div>
  );
}

export default CityCard;
