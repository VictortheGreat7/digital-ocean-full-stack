export function getClockAngles(time) {
  const hours = time.getHours() % 12;
  const minutes = time.getMinutes();
  const seconds = time.getSeconds();

  return {
    hours: (hours * 30) + (minutes * 0.5),
    minutes: (minutes * 6) + (seconds * 0.1),
    seconds: seconds * 6,
  };
}