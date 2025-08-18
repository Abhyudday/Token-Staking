#!/usr/bin/env python3
"""
Health Check Module for Token Holder Bot

Provides health status endpoints for Railway deployment monitoring.
"""

import logging
import psutil
import os
from datetime import datetime
from database import Database
from solscan_api import SolscanAPI
from config import Config

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self):
        self.db = None
        self.solscan = None
        self.start_time = datetime.now()
    
    def get_system_health(self):
        """Get system health metrics"""
        try:
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process info
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Uptime
            uptime = datetime.now() - self.start_time
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": int(uptime.total_seconds()),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available / 1024 / 1024,
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free / 1024 / 1024 / 1024
                },
                "process": {
                    "memory_mb": round(process_memory, 2),
                    "cpu_percent": process.cpu_percent()
                }
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_database_health(self):
        """Get database health status"""
        try:
            if not self.db:
                self.db = Database()
            
            # Test database connection
            with self.db.conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Get basic stats
            total_holders = self.db.get_total_holders()
            threshold = self.db.get_minimum_usd_threshold()
            
            return {
                "status": "healthy",
                "database": "connected",
                "total_holders": total_holders,
                "minimum_usd_threshold": threshold,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_api_health(self):
        """Get SOLSCAN API health status"""
        try:
            if not self.solscan:
                self.solscan = SolscanAPI()
            
            # Test API connection with a simple call
            token_info = self.solscan.get_token_info(Config.TOKEN_CONTRACT_ADDRESS)
            
            if token_info:
                return {
                    "status": "healthy",
                    "api": "connected",
                    "token_name": token_info.get('name', 'Unknown'),
                    "token_symbol": token_info.get('symbol', 'Unknown'),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "warning",
                    "api": "connected",
                    "warning": "No token info returned",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return {
                "status": "unhealthy",
                "api": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_overall_health(self):
        """Get overall health status"""
        system_health = self.get_system_health()
        db_health = self.get_database_health()
        api_health = self.get_api_health()
        
        # Determine overall status
        overall_status = "healthy"
        if db_health["status"] == "unhealthy" or api_health["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif db_health["status"] == "warning" or api_health["status"] == "warning":
            overall_status = "warning"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "system": system_health,
                "database": db_health,
                "api": api_health
            }
        }
    
    def close(self):
        """Close connections"""
        if self.db:
            self.db.close()

# Global health checker instance
health_checker = HealthChecker()

def get_health_status():
    """Get health status for HTTP endpoint"""
    return health_checker.get_overall_health()

def get_health_json():
    """Get health status as JSON string"""
    import json
    return json.dumps(get_health_status(), indent=2)

if __name__ == "__main__":
    # Test health checker
    print("🏥 Health Check Test")
    print("=" * 40)
    
    health = get_health_status()
    print(f"Overall Status: {health['status']}")
    print(f"Database: {health['components']['database']['status']}")
    print(f"API: {health['components']['api']['status']}")
    print(f"System: {health['components']['system']['status']}")
    
    health_checker.close()
