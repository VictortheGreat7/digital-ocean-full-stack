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

// SLO-friendly metrics to populate the Grafana SLO Compliance dashboard
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
      { duration: '2m', target: 500 }, // Start with 500 users
      { duration: '10m', target: 500 }, // Stay at 500 users
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
      { duration: '2m', target: 500 }, // Start with 500 users
      { duration: '5m', target: 750}, // Ramp up to 750 users
      { duration: '5m', target: 1250}, // Ramp up to 1250 users
      { duration: '5m', target: 2500}, // Ramp up to 2500 users
      { duration: '5m', target: 5000}, // Ramp up to 5000 users
      { duration: '10m', target: 5000}, // Stay at 5000 users
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
      { duration: '1m', target: 500 }, // Baseline
      { duration: '5m', target: 5000 }, // Spike to 5000 users
      { duration: '10m', target: 5000 }, // Stay at spike
      { duration: '2m', target: 500 }, // Drop back to baseline
      { duration: '1m', target: 500 }, // Stay at baseline
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
      { duration: '5m', target: 500 }, // Start with 500 users
      { duration: '3h', target: 500 }, // Hold for 3 hours
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
};

export default function () {
  let rand = Math.random();

  if (rand < 0.8) {
    // World Clocks API Endpoint. 80% of traffic, expected to be the most common endpoint hit by users
    group('world clocks endpoint', () => {
      let res = http.get(`${BASE_URL}/api/world-clocks`, {
        tags: { name: 'world-clocks', endpoint: 'world-clocks' },
      });
      check(res, {
        'world clocks status 200': (r) => r.status === 200,
        'world clocks latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'world-clocks', 500);
    });
  } else if (rand < 0.9) {
    // Homepage Endpoint. 10% of traffic, expected to be common but less than API calls
    group('homepage endpoint', () => {
      let res = http.get(`${BASE_URL}/`, {
        tags: { name: 'homepage', endpoint: 'homepage' },
      });
      check(res, {
        'homepage status 200': (r) => r.status === 200,
        'homepage latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'homepage', 500);
    });
  } else {
    // Current Time API Endpoint. Also 10% of traffic, expected to be common but less than world clocks endpoint
    group('time endpoint', () => {
      let tz = TIMEZONES[Math.floor(rand * TIMEZONES.length)];
      let res = http.get(`${BASE_URL}/api/time?timezone=${tz}`, {
        tags: { name: 'time', endpoint: 'time' },
      });
      check(res, {
        'time status 200': (r) => r.status === 200,
        'time latency < 500ms': (r) => r.timings.duration < 500,
      });
      recordSli(res, 'time', 500);
    });
  }

  sleep(1 + rand * 2); // Think time 1-3s
}

export function handleSummary(data) {
  return {
    '/tmp/summary.json': JSON.stringify(data),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}