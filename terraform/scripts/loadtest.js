import http from 'k6/http';
import { check, sleep, group } from 'k6';
// import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

// // Custom metrics for SRE dashboard
// let errorRate = new Rate('errors');
// let latency = new Trend('latency');
// let requestCount = new Counter('requests_total');

const BASE_URL = __ENV.BASE_URL || 'http://localhost';
const TEST_TYPE = __ENV.TEST_TYPE || 'load';

// console.log(`${TEST_TYPE} testing Kronos app on ${BASE_URL}`);

const TIMEZONES = new SharedArray('timezones', function() {
  return [
    'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney',
    'Asia/Dubai', 'Asia/Singapore', 'America/Sao_Paulo', 'Asia/Kolkata',
    'Europe/Paris', 'America/Los_Angeles', 'Asia/Hong_Kong', 'Europe/Berlin'
  ];
});

const profiles = {
  // Expected Normal Load
  load: {
    stages: [
      { duration: '2m', target: 500 }, // Start with 500 users
      { duration: '10m', target: 500 }, // Stay at 500 users
      { duration: '2m', target: 0 }, // Ramp down to 0 users
    ],
    thresholds: {
      'http_req_duration': ['p(95)<2500', 'p(99)<5000'],  // SLO targets
      'http_req_failed': ['rate<0.01'],  // Error rate < 1%
    },
  },

  // Stress Testing to find breaking points
  stress: {
    stages: [
      { duration: '2m', target: 500 }, // Start with 500 users
      { duration: '5m', target: 750}, // Ramp up to 1000 users
      { duration: '5m', target: 1000}, // Ramp up to 1250 users
      { duration: '5m', target: 1250}, // Ramp up to 1500 users
      { duration: '5m', target: 2000}, // Ramp up to 2500 users
      { duration: '10m', target: 2000}, // Stay at 2500 users
      { duration: '5m', target: 0 }, // Recover
    ],
    thresholds: {
      'http_req_duration': ['p(95)<5000', 'p(99)<10000'],  // Relaxed SLO targets
      'http_req_failed': ['rate<0.05'],  // Error rate < 5%
    },
  },

  // Spike Testing for sudden traffic bursts
  spike: {
    stages: [
      { duration: '2m', target: 500 }, // Baseline
      { duration: '2m', target: 2000 }, // Spike to 2000 users
      { duration: '5m', target: 2000 }, // Stay at spike
      { duration: '2m', target: 500 }, // Drop back to baseline
      { duration: '3m', target: 500 }, // Stay at baseline
      { duration: '2m', target: 0 }, // Recover
    ],
    thresholds: {
      'http_req_duration': ['p(95)<5000', 'p(99)<10000'],
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
      'http_req_duration': ['p(95)<2500', 'p(99)<5000'],  // Standard SLO targets
      'http_req_failed': ['rate<0.01'],  // Error rate < 1%
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

  if (rand < 0.95) {
    // Frontend(Homepage). Expected most common endpoint
    group('homepage endpoint', () => {
      let res = http.get(`${BASE_URL}/`, { tags: { name: 'homepage' } });
      check(res, { 'homepage status 200': (r) => r.status === 200 });
    });
  } else if (rand < 0.1) {
    // Current Time API Endpoint. Expected moderate frequency
    group('time endpoint', () => {
      let tz = TIMEZONES[Math.floor(rand * TIMEZONES.length)];
      let res = http.get(`${BASE_URL}/api/time?timezone=${tz}`);
      check(res, { 'time status 200': (r) => r.status === 200 });
    });
  } else {
    // Timezones List API Endpoint. Expected least common
    group('timezones endpoint', () => {
      let res = http.get(`${BASE_URL}/api/timezones`);
      check(res, { 'timezones status 200': (r) => r.status === 200 });
    });
  }

  // errorRate.add(res.status >= 400);
  // latency.add(res.timings.duration);
  // requestCount.add(1);

  sleep(1 + rand * 2); // Think time 1-3s
}

export function handleSummary(data) {
  return {
    '/tmp/summary.json': JSON.stringify(data),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// function customtextSummary(data) {
//   let summary = 'K6 Test Summary\\n';
//   summary += '===============\\n';
//   summary += 'Total Requests: ' + data.metrics.requests_total.value + '\\n';
//   summary += 'Error Rate: ' + (data.metrics.errors.value * 100).toFixed(2) + '%\\n';
//   return summary;
// }