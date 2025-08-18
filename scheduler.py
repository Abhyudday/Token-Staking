import schedule
import time
import logging
import threading
from datetime import datetime
from snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

class SnapshotScheduler:
    def __init__(self):
        self.snapshot_service = SnapshotService()
        self.running = False
        self.thread = None
    
    def start_scheduler(self):
        """Start the scheduler in a separate thread"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("Snapshot scheduler started")
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Snapshot scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        # Schedule daily snapshot at 00:00 UTC
        schedule.every().day.at("00:00").do(self._daily_snapshot)
        
        # Schedule weekly cleanup on Sundays at 02:00 UTC
        schedule.every().sunday.at("02:00").do(self._weekly_cleanup)
        
        # Schedule data validation every 6 hours
        schedule.every(6).hours.do(self._validate_data)
        
        logger.info("Scheduled tasks:")
        logger.info("- Daily snapshot: 00:00 UTC")
        logger.info("- Weekly cleanup: Sunday 02:00 UTC")
        logger.info("- Data validation: Every 6 hours")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def _daily_snapshot(self):
        """Execute daily snapshot"""
        try:
            logger.info("Executing scheduled daily snapshot...")
            start_time = datetime.now()
            
            success = self.snapshot_service.take_daily_snapshot()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if success:
                logger.info(f"Daily snapshot completed successfully in {duration:.2f} seconds")
            else:
                logger.error(f"Daily snapshot failed after {duration:.2f} seconds")
                
        except Exception as e:
            logger.error(f"Error during scheduled daily snapshot: {e}")
    
    def _weekly_cleanup(self):
        """Execute weekly cleanup"""
        try:
            logger.info("Executing scheduled weekly cleanup...")
            
            deleted_count = self.snapshot_service.cleanup_old_snapshots(days_to_keep=90)
            
            logger.info(f"Weekly cleanup completed. Deleted {deleted_count} old snapshots")
            
        except Exception as e:
            logger.error(f"Error during scheduled weekly cleanup: {e}")
    
    def _validate_data(self):
        """Execute data validation"""
        try:
            logger.info("Executing scheduled data validation...")
            
            validation = self.snapshot_service.validate_snapshot_data()
            
            if validation['is_valid']:
                logger.info("Data validation completed successfully")
            else:
                logger.warning(f"Data validation found issues: {validation}")
                
        except Exception as e:
            logger.error(f"Error during scheduled data validation: {e}")
    
    def trigger_manual_snapshot(self):
        """Manually trigger a snapshot (for testing or immediate use)"""
        try:
            logger.info("Manual snapshot triggered...")
            start_time = datetime.now()
            
            success = self.snapshot_service.take_daily_snapshot()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if success:
                logger.info(f"Manual snapshot completed successfully in {duration:.2f} seconds")
                return True
            else:
                logger.error(f"Manual snapshot failed after {duration:.2f} seconds")
                return False
                
        except Exception as e:
            logger.error(f"Error during manual snapshot: {e}")
            return False
    
    def get_next_run_times(self):
        """Get the next scheduled run times"""
        try:
            next_snapshot = schedule.next_run()
            next_cleanup = None
            next_validation = None
            
            # Find next cleanup and validation times
            for job in schedule.jobs:
                if "cleanup" in str(job.job_func):
                    next_cleanup = job.next_run
                elif "validation" in str(job.job_func):
                    next_validation = job.next_run
            
            return {
                "next_snapshot": next_snapshot,
                "next_cleanup": next_cleanup,
                "next_validation": next_validation
            }
            
        except Exception as e:
            logger.error(f"Error getting next run times: {e}")
            return {}
    
    def close(self):
        """Close the scheduler and cleanup"""
        self.stop_scheduler()
        self.snapshot_service.close()

if __name__ == "__main__":
    # Test the scheduler
    scheduler = SnapshotScheduler()
    
    try:
        print("Starting snapshot scheduler...")
        scheduler.start_scheduler()
        
        # Keep running for a while to test
        time.sleep(300)  # Run for 5 minutes
        
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
    finally:
        scheduler.close()
        print("Scheduler stopped")
