import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

// Custom metrics for SRE dashboard
let errorRate = new Rate('errors');
let latency = new Trend('latency');
let requestCount = new Counter('requests_total');

const BASE_URL = __ENV.BASE_URL || 'http://localhost';

const TIMEZONES = [
  'America/New_York', 'Europe/London', 'Asia/Tokyo', 'Australia/Sydney',
  'Asia/Dubai', 'Asia/Singapore', 'America/Sao_Paulo', 'Asia/Kolkata',
  'Europe/Paris', 'America/Los_Angeles', 'Asia/Hong_Kong', 'Europe/Berlin'
];

export let options = {
  stages: [
    { duration: '1m', target: 10 },    // Ramp up to 10 users
    { duration: '3m', target: 30 },    // Ramp to 30 users
    { duration: '2m', target: 50 },    // Spike to 50 users
    { duration: '3m', target: 50 },    // Hold at spike
    { duration: '1m', target: 0 },     // Ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],  // SLO targets
    'errors': ['rate<0.05'],
  },
};

export default function () {
  let rand = Math.random();
  let res;

  group('world-clocks endpoint', () => {
    res = http.get(`${BASE_URL}/world-clocks`);
    check(res, { 'world-clocks status 200': (r) => r.status === 200 });
  });

  group('time endpoint', () => {
    let tz = TIMEZONES[Math.floor(Math.random() * TIMEZONES.length)];
    res = http.get(`${BASE_URL}/time?timezone=${tz}`);
    check(res, { 'time status 200': (r) => r.status === 200 });
  });

  group('timezones endpoint', () => {
    res = http.get(`${BASE_URL}/timezones`);
    check(res, { 'timezones status 200': (r) => r.status === 200 });
  });

  // Intentional errors for error rate testing (5% of traffic)
  if (Math.random() < 0.05) {
    group('error testing', () => {
      res = http.get(`${BASE_URL}/time?timezone=Invalid/Timezone`);
      check(res, { 'error handling 400': (r) => r.status === 400 });
    });
  }

  errorRate.add(res.status >= 400);
  latency.add(res.timings.duration);
  requestCount.add(1);

  sleep(Math.random() * 2); // Think time 0-2s
}

export function handleSummary(data) {
  return {
    '/tmp/summary.json': JSON.stringify(data),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  let summary = 'K6 Test Summary\\n';
  summary += '===============\\n';
  summary += 'Total Requests: ' + data.metrics.requests_total.value + '\\n';
  summary += 'Error Rate: ' + (data.metrics.errors.value * 100).toFixed(2) + '%\\n';
  return summary;
}