# Health Check System

This document describes the comprehensive health check system implemented for the Telegram Rewards Bot.

## Overview

The health check system provides multiple endpoints to monitor the application's health and readiness status. It checks all critical services including the database, bot, dispatcher, and blockchain monitor.

## Health Check Endpoints

### 1. Root Endpoint (`/`)
- **Purpose**: Basic availability check
- **Response**: `OK` (200) or connection error
- **Use Case**: Simple uptime monitoring

### 2. Simple Health Check (`/health/simple`)
- **Purpose**: Basic health status
- **Response**: `OK` (200) or connection error
- **Use Case**: Load balancer health checks

### 3. Readiness Check (`/health/ready`)
- **Purpose**: Verify application is ready to serve requests
- **Response**: 
  - `READY` (200) - Application is fully initialized
  - `NOT_READY` (503) - Application is still starting up
- **Use Case**: Kubernetes readiness probes, Docker health checks

### 4. Comprehensive Health Check (`/health`)
- **Purpose**: Detailed health status of all services
- **Response**: JSON with detailed service status
- **HTTP Status**: 
  - 200 - All services healthy
  - 503 - Some services unhealthy
  - 500 - Health check system error
- **Use Case**: Detailed monitoring, debugging

## Health Check Response Format

### Successful Response (200)
```json
{
  "status": "healthy",
  "timestamp": 1234567890.123,
  "services": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "blockchain_monitor": {
      "status": "healthy",
      "message": "Blockchain monitor is active"
    },
    "bot": {
      "status": "healthy",
      "message": "Bot is running",
      "bot_id": 123456789,
      "bot_username": "your_bot_username"
    },
    "dispatcher": {
      "status": "healthy",
      "message": "Dispatcher is running"
    }
  },
  "http_status": 200
}
```

### Unhealthy Response (503)
```json
{
  "status": "unhealthy",
  "timestamp": 1234567890.123,
  "services": {
    "database": {
      "status": "unhealthy",
      "message": "Database connection failed"
    },
    "blockchain_monitor": {
      "status": "healthy",
      "message": "Blockchain monitor is active"
    },
    "bot": {
      "status": "healthy",
      "message": "Bot is running"
    },
    "dispatcher": {
      "status": "healthy",
      "message": "Dispatcher is running"
    }
  },
  "http_status": 503
}
```

## Docker Health Check

Use the provided `docker-healthcheck.sh` script in your Dockerfile:

```dockerfile
# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Copy health check script
COPY docker-healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-healthcheck.sh

# Set health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD /usr/local/bin/docker-healthcheck.sh
```

## Kubernetes Configuration

### Liveness Probe
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
```

### Readiness Probe
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## Railway Configuration

For Railway deployments, the health check system automatically integrates with the platform's health check mechanism. The `/health` endpoint will be used by Railway to determine if your service is healthy.

## Testing

Use the provided test script to verify health check endpoints:

```bash
python test_health.py
```

## Implementation Details

### Health Checker Class
The `HealthChecker` class manages all health check operations:
- **Database Check**: Verifies database connectivity with a simple query
- **Bot Check**: Confirms bot is running and accessible
- **Dispatcher Check**: Ensures message dispatcher is active
- **Blockchain Monitor Check**: Verifies blockchain monitoring is active

### Service Integration
Health checks are automatically configured when the application starts:
1. Services are initialized in the lifespan context
2. Health checker references are set
3. Health check endpoints become active after a 2-second startup delay

### Error Handling
- All health checks run concurrently using `asyncio.gather`
- Exceptions are caught and converted to unhealthy status
- HTTP status codes are automatically set based on health status

## Troubleshooting

### Health Check Failing
1. Check application logs for startup errors
2. Verify all required environment variables are set
3. Ensure database is accessible
4. Check if bot token is valid

### Service Not Ready
1. Wait for the 2-second startup delay
2. Check if all services are properly initialized
3. Verify database connection string
4. Check bot token permissions

### Performance Issues
- Health checks run concurrently for optimal performance
- Simple endpoints (`/`, `/health/simple`) are lightweight
- Comprehensive health check (`/health`) includes all service checks
- Readiness check (`/health/ready`) is optimized for frequent polling

## Monitoring Integration

The health check system can be integrated with:
- **Prometheus**: Use `/health` endpoint for metrics
- **Grafana**: Create dashboards based on health status
- **Alerting**: Set up alerts for unhealthy status
- **Load Balancers**: Use `/health/simple` for backend health checks 