import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// Configure the tracer provider
const provider = new WebTracerProvider({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'kronos-frontend',
    [SemanticResourceAttributes.SERVICE_NAMESPACE]: 'kronos',
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'development',
  }),
});

// Configure OTLP exporter - use backend as proxy to Tempo
const exporter = new OTLPTraceExporter({
  url:  `${window.location.origin}/api/frontend-traces`
});

// Add span processor
provider.addSpanProcessor(new BatchSpanProcessor(exporter, {
  onStart(span) { console.log('span started:', span.name); },
  onEnd(span) { console.log('span ended:', span.name); }
}));

// Register the provider
provider.register();

// Auto-instrument the application
registerInstrumentations({
  instrumentations: [
    getWebAutoInstrumentations({
      '@opentelemetry/instrumentation-document-load': {},
      '@opentelemetry/instrumentation-user-interaction': {},
      '@opentelemetry/instrumentation-fetch': {},
      '@opentelemetry/instrumentation-xml-http-request': {},
    }),
  ],
});

export default provider;