// import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
// import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
// import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
// import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
// import { registerInstrumentations } from '@opentelemetry/instrumentation';
// import { Resource } from '@opentelemetry/resources';
// import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// // Configure the tracer provider
// const provider = new WebTracerProvider({
//   resource: new Resource({
//     [SemanticResourceAttributes.SERVICE_NAME]: 'kronos-frontend',
//     [SemanticResourceAttributes.SERVICE_NAMESPACE]: 'kronos',
//     [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'development',
//   }),
// });

// // Configure OTLP exporter - use backend as proxy to Tempo
// const exporter = new OTLPTraceExporter({
//   url:  `${window.location.origin}/api/frontend-traces`
// });

// // Add span processor
// provider.addSpanProcessor(new BatchSpanProcessor(exporter, {
//   onStart(span) { console.log('span started:', span.name); },
//   onEnd(span) { console.log('span ended:', span.name); }
// }));

// // Register the provider
// provider.register();

// // Auto-instrument the application
// registerInstrumentations({
//   instrumentations: [
//     getWebAutoInstrumentations({
//       '@opentelemetry/instrumentation-document-load': {},
//       '@opentelemetry/instrumentation-user-interaction': {},
//       '@opentelemetry/instrumentation-fetch': {},
//       '@opentelemetry/instrumentation-xml-http-request': {},
//     }),
//   ],
// });

// export default provider;


import { datadogRum } from '@datadog/browser-rum'

datadogRum.init({
  applicationId: import.meta.env.VITE_DD_APP_ID,
  clientToken: import.meta.env.VITE_DD_CLIENT_TOKEN,
  site: 'us5.datadoghq.com',
  service: 'kronos-frontend',
  env: 'dev',
  version: '1.0.0',
  sessionSampleRate: 100,
  sessionReplaySampleRate: 20, // set >0 if you want Session Replay
  trackUserInteractions: true,
  trackResources: true,
  trackLongTasks: true,
  trackBfcacheViews: true,
  defaultPrivacyLevel: 'mask-user-input',
  // Distributed tracing — connects frontend spans to backend traces
  allowedTracingUrls: [
    // Match your API origin; this injects trace headers on outgoing requests
    { match: /\/api\//, propagatorTypes: ['datadog', 'tracecontext'] },
    // If you also call the backend directly in dev:
    { match: 'http://localhost:5000', propagatorTypes: ['datadog', 'tracecontext'] },
    window.location.origin, // if API is same-origin
  ],
  traceSampleRate: 100,    // % of requests to trace
})

// optional if Session Replay is enabled
datadogRum.startSessionReplayRecording()
