import { useState, useEffect, useCallback, useRef } from 'react';
import CityCard from './CityCard';
import './Dashboard.css';

const API_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.DEV ? 'http://localhost:5000' : ''
);

function Dashboard() {
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [searchTerm, setSearchTerm] = useState('');
  const searchRef = useRef(''); // Silently tracks search for the interval
  
  const [is24Hour, setIs24Hour] = useState(true);
  const debounceRef = useRef(null);

  const fetchWorldClocks = useCallback(async (query = '', isBackgroundPoll = false) => {
    // Only show the loading spinner if this is a direct user action or initial load
    if (!isBackgroundPoll) {
      setLoading(true);
    }
    setError(null);

    try {
      const url = query
        ? `${API_URL}/world-clocks?search=${encodeURIComponent(query)}`
        : `${API_URL}/world-clocks`;
      
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch world clocks: ${response.status}`);
      }
      const data = await response.json();
      setCities(data.cities);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!isBackgroundPoll) {
        setLoading(false);
      }
    }
  }, []);

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchTerm(value);
    searchRef.current = value; 

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      // Direct user action, so isBackgroundPoll defaults to false
      fetchWorldClocks(value); 
    }, 300);
  };

  useEffect(() => {
    // Initial fetch on mount
    fetchWorldClocks('');

    const interval = setInterval(() => {
      // Check the ref. Only poll if the search bar is empty.
      if (!searchRef.current) {
        // Pass `true` so the background poll happens silently without triggering the loading UI
        fetchWorldClocks('', true); 
      }
    }, 75000);

    return () => {
      clearInterval(interval);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [fetchWorldClocks]);

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
          <button onClick={() => fetchWorldClocks(searchTerm)}>Retry</button>
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

      {cities.length === 0 && (
        <div className="no-results">
          <p>No cities found matching "{searchTerm}"</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
