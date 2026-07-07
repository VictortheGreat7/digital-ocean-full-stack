import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost';
const TEST_TYPE = __ENV.TEST_TYPE || 'load';

const TIMEZONES = new SharedArray('timezones', function() {
  return [
    'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney',
    'Asia/Dubai', 'Asia/Singapore', 'America/Sao_Paulo', 'Asia/Kolkata',
    'Europe/Paris', 'America/Los_Angeles', 'Asia/Hong_Kong', 'Europe/Berlin'
  ];
});

const SEARCH_QUERIES = new SharedArray('searchQueries', function() {
  return [
    'lagos', 'london', 'tokyo', 'new york', 'africa', 
    'america', 'pacific', 'lon', 'ber', 'syd', 'dub', 'los',
    'x' // Intentionally testing a query that might return few/no results
  ];
});

// Custom Metrics
const sliErrorBudgetBurn = new Rate('sli_error_budget_burn');
const sliLatencyVsSloRatio = new Trend('sli_latency_vs_slo_ratio');
const sliRequestCount = new Counter('sli_request_count');

function recordSli(res, endpoint, latencySloMs) {
  const latency = res.timings.duration;
  const success = res.status >= 200 && res.status < 400;
  const tags = { endpoint };

  sliRequestCount.add(1, tags);
  sliErrorBudgetBurn.add(!success, tags);

  if (latencySloMs > 0) {
    sliLatencyVsSloRatio.add(latency / latencySloMs, tags);
  }
}

const profiles = {
  // Expected Normal Load
  load: {
    stages: [
      { duration: '3m', target: 2500 }, // Start with 2500 users
      { duration: '15m', target: 2500 }, // Stay at 2500 users
      { duration: '2m', target: 0 }, // Ramp down to 0 users
    ],
    thresholds: {
      'http_req_duration': ['p(95)<500', 'p(99)<1000'],  // SLO targets
      'http_req_failed': ['rate<0.001'],  // Error rate < 0.1%
      'sli_error_budget_burn': ['rate<0.001'],
      'sli_latency_vs_slo_ratio': ['p(95)<1.0'],
    },
  },

  // Stress Testing to find breaking points
  stress: {
    stages: [
      { duration: '2m', target: 250 }, // Start with 250 users
      { duration: '5m', target: 500}, // Ramp up to 500 users
      { duration: '5m', target: 750}, // Ramp up to 750 users
      { duration: '5m', target: 1500}, // Ramp up to 1500 users
      { duration: '5m', target: 3000}, // Ramp up to 3000 users
      { duration: '10m', target: 3000}, // Stay at 3000 users
      { duration: '5m', target: 0 }, // Recover
    ],
    thresholds: {
      'http_req_duration': ['p(95)<2000', 'p(99)<5000'],  // Relaxed SLO targets
      'http_req_failed': ['rate<0.05'],  // Error rate < 5%
    },
  },

  // Spike Testing for sudden traffic bursts
  spike: {
    stages: [
      { duration: '1m', target: 2000 }, // Baseline
      { duration: '5m', target: 3000 }, // Spike to 4000 users
      { duration: '10m', target: 3000 }, // Stay at spike
      { duration: '2m', target: 2000 }, // Drop back to baseline
      { duration: '1m', target: 2000 }, // Stay at baseline
      { duration: '1m', target: 0 }, // Recover
    ],
    thresholds: {
      'http_req_duration': ['p(95)<2000', 'p(99)<5000'],
      'http_req_failed': ['rate<0.10'],  // Error rate < 10%
    },
  },

  // Soak Testing for long-term stability
  soak: {
    stages: [
      { duration: '5m', target: 2000 }, // Start with 2000 users
      { duration: '3h', target: 2000 }, // Hold for 3 hours
      { duration: '5m', target: 0 }, // Ramp down to 0 users
    ],
    thresholds: {
      'http_req_duration': ['p(95)<500', 'p(99)<1000'],  // Standard SLO targets
      'http_req_failed': ['rate<0.01'],  // Error rate < 1%
      'sli_error_budget_burn': ['rate<0.001'],
      'sli_latency_vs_slo_ratio': ['p(95)<1.0'],
    },
  },
};

const selectedProfile = profiles[TEST_TYPE];

export let options = {
  ...selectedProfile,
  tags: {
    test_type: TEST_TYPE,
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)", "p(99.99)", "count"],
};

export default function () {
  // Generate a SINGLE random number to accurately route traffic
  const rand = Math.random(); 

  if (rand < 0.75) {
    // 75% of traffic: Cached World Clocks (The "Appetizer" fast path)
    group('world clocks endpoint', () => {
      let res = http.get(`${BASE_URL}/world-clocks`, {
        tags: { name: 'world-clocks', endpoint: 'world-clocks' },
      });
      check(res, {
        'world clocks status 200': (r) => r.status === 200,
        'world clocks latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'world-clocks', 500);
    });

  } else if (rand < 0.85) {
    // 10% of traffic: Dynamic Search (The "Menu" CPU-bound path)
    group('dashboard search endpoint', () => {
      let query = SEARCH_QUERIES[Math.floor(Math.random() * SEARCH_QUERIES.length)];
      let res = http.get(`${BASE_URL}/world-clocks?search=${encodeURIComponent(query)}`, {
        // Tagging this differently so it doesn't skew your cached world-clocks metrics
        tags: { name: 'world-clocks-search', endpoint: 'world-clocks-search' }, 
      });
      check(res, {
        'search status 200': (r) => r.status === 200,
        'search latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'world-clocks-search', 500);
    });

  } else if (rand < 0.95) {
    // 10% of traffic: Timezones Endpoint
    group('timezones endpoint', () => {
      let res = http.get(`${BASE_URL}/timezones`, {
        tags: { name: 'timezones', endpoint: 'timezones' },
      });
      check(res, {
        'timezones status 200': (r) => r.status === 200,
        'timezones latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'timezones', 500);
    });

  } else {
    // 5% of traffic: Specific Time Endpoint
    group('time endpoint', () => {
      let tz = TIMEZONES[Math.floor(Math.random() * TIMEZONES.length)];
      let res = http.get(`${BASE_URL}/time?timezone=${tz}`, {
        tags: { name: 'time', endpoint: 'time' },
      });
      check(res, {
        'time status 200': (r) => r.status === 200,
        'time latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'time', 500);
    });
  }

  sleep(1 + Math.random() * 2); // Think time 1-3s
}

export function handleSummary(data) {
  return {
    '/tmp/summary.json': JSON.stringify(data),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}
