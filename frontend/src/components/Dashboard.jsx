import { useState } from 'react';
import CityCard from './CityCard';
import useWorldClocks from '../hooks/useWorldClocks';
import './Dashboard.css';

function Dashboard() {
  const {
    cities,
    count,
    loading,
    error,
    searchTerm,
    handleSearchChange,
    retry,
  } = useWorldClocks();

  const [is24Hour, setIs24Hour] = useState(true);

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
          <button onClick={retry}>Retry</button>
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
              // Updated to use the debounce function
              onChange={handleSearchChange}
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
        {/* Render directly from the 'cities' state */}
        {cities.map((city, index) => (
          <CityCard
            key={city.city}
            city={city}
            is24Hour={is24Hour}
            animationDelay={index * 0.1}
          />
        ))}
      </div>

      {count === 0 && (
        <div className="no-results">
          <p>No cities found matching "{searchTerm}"</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
