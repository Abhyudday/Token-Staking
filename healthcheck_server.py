#!/usr/bin/env python3
"""
Health Check HTTP Server for Token Holder Bot

Provides HTTP endpoints for Railway health monitoring.
"""

import http.server
import socketserver
import json
import logging
from urllib.parse import urlparse, parse_qs
from healthcheck import get_health_status, get_health_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == "/health":
                self._handle_health_check()
            elif path == "/":
                self._handle_root()
            else:
                self._handle_not_found()
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self._send_error_response(500, "Internal Server Error")
    
    def _handle_health_check(self):
        """Handle /health endpoint"""
        try:
            health_data = get_health_status()
            
            # Set response headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Send response
            response = json.dumps(health_data, indent=2)
            self.wfile.write(response.encode('utf-8'))
            
            logger.info(f"Health check request - Status: {health_data['status']}")
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            self._send_error_response(500, "Health check failed")
    
    def _handle_root(self):
        """Handle root endpoint"""
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Token Holder Bot - Health Status</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                    .healthy { background-color: #d4edda; color: #155724; }
                    .warning { background-color: #fff3cd; color: #856404; }
                    .unhealthy { background-color: #f8d7da; color: #721c24; }
                    .endpoint { background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
                </style>
            </head>
            <body>
                <h1>🏥 Token Holder Bot Health Status</h1>
                <p>This service provides health monitoring for the Token Holder Bot.</p>
                
                <div class="endpoint">
                    <h3>📊 Health Check Endpoint</h3>
                    <p><strong>GET /health</strong> - Returns comprehensive health status</p>
                    <p>Use this endpoint for Railway health monitoring.</p>
                </div>
                
                <div class="endpoint">
                    <h3>🔍 Current Status</h3>
                    <div id="current-status">Loading...</div>
                </div>
                
                <script>
                    // Fetch current health status
                    fetch('/health')
                        .then(response => response.json())
                        .then(data => {
                            const statusDiv = document.getElementById('current-status');
                            const statusClass = data.status === 'healthy' ? 'healthy' : 
                                              data.status === 'warning' ? 'warning' : 'unhealthy';
                            
                            statusDiv.innerHTML = `
                                <div class="status ${statusClass}">
                                    <strong>Overall Status:</strong> ${data.status.toUpperCase()}<br>
                                    <strong>Timestamp:</strong> ${data.timestamp}<br>
                                    <strong>Database:</strong> ${data.components.database.status}<br>
                                    <strong>API:</strong> ${data.components.api.status}<br>
                                    <strong>System:</strong> ${data.components.system.status}
                                </div>
                            `;
                        })
                        .catch(error => {
                            document.getElementById('current-status').innerHTML = 
                                '<div class="status unhealthy">Error fetching status</div>';
                        });
                </script>
            </body>
            </html>
            """
            
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error in root handler: {e}")
            self._send_error_response(500, "Internal Server Error")
    
    def _handle_not_found(self):
        """Handle 404 errors"""
        self._send_error_response(404, "Not Found")
    
    def _send_error_response(self, code, message):
        """Send error response"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error_data = {
            "error": message,
            "status_code": code,
            "path": self.path
        }
        
        response = json.dumps(error_data, indent=2)
        self.wfile.write(response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override logging to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

def run_health_server(port=8000):
    """Run the health check server"""
    try:
        with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
            logger.info(f"Health check server started on port {port}")
            logger.info(f"Health endpoint: http://localhost:{port}/health")
            logger.info(f"Root endpoint: http://localhost:{port}/")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Health check server stopped by user")
    except Exception as e:
        logger.error(f"Error running health server: {e}")

if __name__ == "__main__":
    import sys
    
    # Get port from command line or use default
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    
    print(f"🏥 Starting Health Check Server on port {port}")
    print(f"📊 Health endpoint: http://localhost:{port}/health")
    print(f"🌐 Root endpoint: http://localhost:{port}/")
    print("Press Ctrl+C to stop")
    
    run_health_server(port)
