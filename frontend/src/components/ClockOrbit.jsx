import { useEffect, useState } from 'react';
import './ClockOrbit.css';

function ClockOrbit({ time, colorScheme }) {
  const [angles, setAngles] = useState({
    hours: 0,
    minutes: 0,
    seconds: 0
  });

  useEffect(() => {
    const hours = time.getHours() % 12;
    const minutes = time.getMinutes();
    const seconds = time.getSeconds();

    setAngles({
      hours: (hours * 30) + (minutes * 0.5),
      minutes: (minutes * 6) + (seconds * 0.1),
      seconds: seconds * 6
    });
  }, [time]);

  return (
    <div className="clock-orbit">
      <div className="orbit-container">
        {/* Outer orbit rings */}
        <div className="orbit-ring orbit-ring-1"></div>
        <div className="orbit-ring orbit-ring-2"></div>
        <div className="orbit-ring orbit-ring-3"></div>

        {/* Clock face */}
        <div className="clock-face">
          {/* Hour markers */}
          {[...Array(12)].map((_, i) => (
            <div
              key={i}
              className="hour-marker"
              style={{
                transform: `rotate(${i * 30}deg) translateY(-45px)`
              }}
            >
              <div className="marker-dot"></div>
            </div>
          ))}

          {/* Clock hands */}
          <div
            className="clock-hand hour-hand"
            style={{
              transform: `rotate(${angles.hours}deg)`,
              backgroundColor: colorScheme.primary
            }}
          ></div>

          <div
            className="clock-hand minute-hand"
            style={{
              transform: `rotate(${angles.minutes}deg)`,
              backgroundColor: colorScheme.secondary
            }}
          ></div>

          <div
            className="clock-hand second-hand"
            style={{
              transform: `rotate(${angles.seconds}deg)`
            }}
          ></div>

          {/* Center dot */}
          <div 
            className="clock-center"
            style={{
              backgroundColor: colorScheme.primary
            }}
          ></div>
        </div>

        {/* Orbiting planets */}
        <div 
          className="orbit-planet planet-1"
          style={{ backgroundColor: colorScheme.primary }}
        ></div>
        <div 
          className="orbit-planet planet-2"
          style={{ backgroundColor: colorScheme.secondary }}
        ></div>
      </div>
    </div>
  );
}

export default ClockOrbit;
