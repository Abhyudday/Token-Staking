import psycopg2
import psycopg2.extras
from datetime import datetime, date
from config import Config
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(Config.DATABASE_URL)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            with self.conn.cursor() as cursor:
                # Create holders table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS holders (
                        id SERIAL PRIMARY KEY,
                        wallet_address VARCHAR(44) UNIQUE NOT NULL,
                        token_balance DECIMAL(20, 8) NOT NULL,
                        usd_value DECIMAL(15, 2),
                        first_seen_date DATE NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create snapshots table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id SERIAL PRIMARY KEY,
                        wallet_address VARCHAR(44) NOT NULL,
                        snapshot_date DATE NOT NULL,
                        token_balance DECIMAL(20, 8) NOT NULL,
                        usd_value DECIMAL(15, 2),
                        days_held INTEGER NOT NULL,
                        FOREIGN KEY (wallet_address) REFERENCES holders(wallet_address),
                        UNIQUE(wallet_address, snapshot_date)
                    )
                """)
                
                # Create settings table for admin configuration
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        id SERIAL PRIMARY KEY,
                        key VARCHAR(50) UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert default minimum USD threshold if not exists
                cursor.execute("""
                    INSERT INTO settings (key, value) 
                    VALUES ('minimum_usd_threshold', '0')
                    ON CONFLICT (key) DO NOTHING
                """)
                
                self.conn.commit()
                logger.info("Database tables created successfully")
                
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise
    
    def get_minimum_usd_threshold(self):
        """Get the minimum USD threshold from settings"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT value FROM settings WHERE key = 'minimum_usd_threshold'")
                result = cursor.fetchone()
                return float(result[0]) if result else 0
        except Exception as e:
            logger.error(f"Error getting minimum USD threshold: {e}")
            return 0
    
    def set_minimum_usd_threshold(self, threshold):
        """Set the minimum USD threshold"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE settings SET value = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'minimum_usd_threshold'
                """, (str(threshold),))
                self.conn.commit()
                logger.info(f"Minimum USD threshold updated to {threshold}")
                return True
        except Exception as e:
            logger.error(f"Error setting minimum USD threshold: {e}")
            self.conn.rollback()
            return False
    
    def upsert_holder(self, wallet_address, token_balance, usd_value):
        """Insert or update holder information"""
        try:
            with self.conn.cursor() as cursor:
                # Check if holder exists
                cursor.execute("SELECT first_seen_date FROM holders WHERE wallet_address = %s", (wallet_address,))
                result = cursor.fetchone()
                
                if result:
                    # Update existing holder
                    cursor.execute("""
                        UPDATE holders 
                        SET token_balance = %s, usd_value = %s, last_updated = CURRENT_TIMESTAMP
                        WHERE wallet_address = %s
                    """, (token_balance, usd_value, wallet_address))
                    first_seen_date = result[0]
                else:
                    # Insert new holder
                    first_seen_date = date.today()
                    cursor.execute("""
                        INSERT INTO holders (wallet_address, token_balance, usd_value, first_seen_date)
                        VALUES (%s, %s, %s, %s)
                    """, (wallet_address, token_balance, usd_value, first_seen_date))
                
                self.conn.commit()
                return first_seen_date
                
        except Exception as e:
            logger.error(f"Error upserting holder: {e}")
            self.conn.rollback()
            raise
    
    def add_snapshot(self, wallet_address, token_balance, usd_value, days_held):
        """Add a daily snapshot for a holder"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO snapshots (wallet_address, snapshot_date, token_balance, usd_value, days_held)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (wallet_address, snapshot_date) 
                    DO UPDATE SET 
                        token_balance = EXCLUDED.token_balance,
                        usd_value = EXCLUDED.usd_value,
                        days_held = EXCLUDED.days_held
                """, (wallet_address, date.today(), token_balance, usd_value, days_held))
                
                self.conn.commit()
                logger.info(f"Snapshot added for {wallet_address}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding snapshot: {e}")
            self.conn.rollback()
            return False
    
    def get_leaderboard(self, limit=50):
        """Get leaderboard ranked by days held"""
        try:
            threshold = self.get_minimum_usd_threshold()
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        h.wallet_address,
                        h.token_balance,
                        h.usd_value,
                        h.first_seen_date,
                        COALESCE(MAX(s.days_held), 0) as days_held
                    FROM holders h
                    LEFT JOIN snapshots s ON h.wallet_address = s.wallet_address
                    WHERE h.usd_value >= %s
                    GROUP BY h.wallet_address, h.token_balance, h.usd_value, h.first_seen_date
                    ORDER BY days_held DESC, h.usd_value DESC
                    LIMIT %s
                """, (threshold, limit))
                
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []
    
    def get_holder_rank(self, wallet_address):
        """Get the rank of a specific holder"""
        try:
            threshold = self.get_minimum_usd_threshold()
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    WITH ranked_holders AS (
                        SELECT 
                            h.wallet_address,
                            COALESCE(MAX(s.days_held), 0) as days_held,
                            ROW_NUMBER() OVER (ORDER BY COALESCE(MAX(s.days_held), 0) DESC, h.usd_value DESC) as rank
                        FROM holders h
                        LEFT JOIN snapshots s ON h.wallet_address = s.wallet_address
                        WHERE h.usd_value >= %s
                        GROUP BY h.wallet_address, h.usd_value
                    )
                    SELECT rank, days_held FROM ranked_holders WHERE wallet_address = %s
                """, (threshold, wallet_address))
                
                result = cursor.fetchone()
                return result if result else (None, 0)
                
        except Exception as e:
            logger.error(f"Error getting holder rank: {e}")
            return (None, 0)
    
    def get_total_holders(self):
        """Get total number of holders above threshold"""
        try:
            threshold = self.get_minimum_usd_threshold()
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM holders WHERE usd_value >= %s
                """, (threshold,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting total holders: {e}")
            return 0
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
