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
  // Use a ref to track the search term for the background interval 
  // without triggering the useEffect to re-run
  const searchRef = useRef(''); 
  
  const [is24Hour, setIs24Hour] = useState(true);
  const debounceRef = useRef(null);

  const fetchWorldClocks = useCallback(async (query = '') => {
    if (!cities.length) setLoading(true);
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
      setLoading(false);
    }
  }, [cities.length]);

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchTerm(value);
    searchRef.current = value; // Silently update the ref for the interval to read

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      fetchWorldClocks(value);
    }, 300);
  };

  useEffect(() => {
    // 1. Initial fetch on component mount only
    fetchWorldClocks('');

    // 2. Set up the 75-second polling interval
    const interval = setInterval(() => {
      // Check the ref to see if the user is currently searching
      if (!searchRef.current) {
        fetchWorldClocks('');
      }
    }, 75000);

    // 3. Cleanup
    return () => {
      clearInterval(interval);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [fetchWorldClocks]); // Notice searchTerm is entirely removed from here

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
