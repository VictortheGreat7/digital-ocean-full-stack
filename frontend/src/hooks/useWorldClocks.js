import { useCallback, useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.DEV ? 'http://localhost:5000' : ''
);

const DEBOUNCE_MS = 300;
const POLL_INTERVAL_MS = 75000;

function useWorldClocks() {
  const [cities, setCities] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const searchRef = useRef('');
  const debounceRef = useRef(null);

  const fetchWorldClocks = useCallback(async (query = '', isBackgroundPoll = false) => {
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
      setCities(data.cities ?? []);
      setCount(data.count ?? 0);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!isBackgroundPoll) {
        setLoading(false);
      }
    }
  }, []);

  const handleSearchChange = useCallback(
    (event) => {
      const value = event.target.value;
      setSearchTerm(value);
      searchRef.current = value;

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      debounceRef.current = setTimeout(() => {
        fetchWorldClocks(value);
      }, DEBOUNCE_MS);
    },
    [fetchWorldClocks],
  );

  const retry = useCallback(() => {
    fetchWorldClocks(searchTerm);
  }, [fetchWorldClocks, searchTerm]);

  useEffect(() => {
    fetchWorldClocks('');

    const interval = setInterval(() => {
      if (!searchRef.current) {
        fetchWorldClocks('', true);
      }
    }, POLL_INTERVAL_MS);

    return () => {
      clearInterval(interval);

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [fetchWorldClocks]);

  return {
    cities,
    count,
    loading,
    error,
    searchTerm,
    handleSearchChange,
    retry,
  };
}

export default useWorldClocks;