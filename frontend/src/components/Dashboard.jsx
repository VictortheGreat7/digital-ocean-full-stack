import { useState, useEffect } from 'react';
import CityCard from './CityCard';
import './Dashboard.css';

// In production, the API is behind the same ingress at /api
// In development, use localhost:5000
const API_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.DEV ? 'http://localhost:5000' : ''
);

function Dashboard() {
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [is24Hour, setIs24Hour] = useState(true);

  useEffect(() => {
    fetchWorldClocks();
    // Update clocks every 75 seconds
    const interval = setInterval(fetchWorldClocks, 75000);
    return () => clearInterval(interval);
  }, []);

  const fetchWorldClocks = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/world-clocks`);
      if (!response.ok) {
        throw new Error(`Failed to fetch world clocks: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      setCities(data.cities);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredCities = cities.filter(city =>
    city.city.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading">
          <div className="loading-spinner"></div>
          <p>Loading world clocks...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={fetchWorldClocks}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <h1 className="dashboard-title">
            <span className="planet-icon">🌍</span>
            World Clock Dashboard
          </h1>
          <p className="dashboard-subtitle">Track time across the globe</p>
        </div>
        
        <div className="controls">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search cities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
          
          <button
            className={`toggle-button ${is24Hour ? 'active' : ''}`}
            onClick={() => setIs24Hour(!is24Hour)}
          >
            {is24Hour ? '24h' : '12h'}
          </button>
        </div>
      </header>

      <div className="cities-grid">
        {filteredCities.map((city, index) => (
          <CityCard
            key={city.city}
            city={city}
            is24Hour={is24Hour}
            animationDelay={index * 0.1}
          />
        ))}
      </div>

      {filteredCities.length === 0 && (
        <div className="no-results">
          <p>No cities found matching "{searchTerm}"</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
