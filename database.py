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
                        token_balance DECIMAL(30, 8) NOT NULL,
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
                        token_balance DECIMAL(30, 8) NOT NULL,
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
                
                # Run migrations for existing tables
                self._run_migrations()
                
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise
    
    def _run_migrations(self):
        """Run database migrations for existing tables"""
        try:
            with self.conn.cursor() as cursor:
                # Check if we need to migrate token_balance precision
                cursor.execute("""
                    SELECT column_name, data_type, numeric_precision, numeric_scale
                    FROM information_schema.columns 
                    WHERE table_name = 'holders' AND column_name = 'token_balance'
                """)
                result = cursor.fetchone()
                
                if result and result[2] < 30:  # precision < 30
                    logger.info("Migrating token_balance precision from DECIMAL(20,8) to DECIMAL(30,8)")
                    cursor.execute("""
                        ALTER TABLE holders 
                        ALTER COLUMN token_balance TYPE DECIMAL(30, 8)
                    """)
                    cursor.execute("""
                        ALTER TABLE snapshots 
                        ALTER COLUMN token_balance TYPE DECIMAL(30, 8)
                    """)
                    self.conn.commit()
                    logger.info("Migration completed successfully")
                
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            self.conn.rollback()
    
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
            logger.info(f"Fetching leaderboard with threshold: ${threshold}")
            
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
                
                results = cursor.fetchall()
                logger.info(f"Leaderboard query returned {len(results)} results")
                
                if not results:
                    logger.warning(f"No holders found above threshold ${threshold}")
                    # Check if there are any holders at all
                    cursor.execute("SELECT COUNT(*) FROM holders")
                    total_holders = cursor.fetchone()[0]
                    logger.info(f"Total holders in database: {total_holders}")
                    
                    if total_holders > 0:
                        # Check what the highest USD value is
                        cursor.execute("SELECT MAX(usd_value) FROM holders")
                        max_usd = cursor.fetchone()[0]
                        logger.info(f"Highest USD value in database: ${max_usd}")
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            return []
    
    def get_holder_rank(self, wallet_address):
        """Get the rank of a specific holder"""
        try:
            threshold = self.get_minimum_usd_threshold()
            logger.info(f"Getting rank for wallet {wallet_address[:8]}...{wallet_address[-8:]} with threshold ${threshold}")
            
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
                if result:
                    rank, days_held = result
                    logger.info(f"Wallet rank: {rank}, days held: {days_held}")
                else:
                    logger.warning(f"Wallet not found in ranked results")
                    # Check if wallet exists at all
                    cursor.execute("SELECT usd_value FROM holders WHERE wallet_address = %s", (wallet_address,))
                    wallet_check = cursor.fetchone()
                    if wallet_check:
                        usd_value = wallet_check[0]
                        logger.info(f"Wallet exists but below threshold. USD value: ${usd_value}, threshold: ${threshold}")
                    else:
                        logger.warning(f"Wallet not found in holders table")
                
                return result if result else (None, 0)
                
        except Exception as e:
            logger.error(f"Error getting holder rank: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            return (None, 0)
    
    def get_total_holders(self):
        """Get total number of holders above threshold"""
        try:
            threshold = self.get_minimum_usd_threshold()
            logger.info(f"Getting total holders count with threshold: ${threshold}")
            
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM holders WHERE usd_value >= %s
                """, (threshold,))
                count = cursor.fetchone()[0]
                logger.info(f"Total holders above threshold: {count}")
                
                # Also log total holders regardless of threshold
                cursor.execute("SELECT COUNT(*) FROM holders")
                total_count = cursor.fetchone()[0]
                logger.info(f"Total holders in database: {total_count}")
                
                return count
        except Exception as e:
            logger.error(f"Error getting total holders: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            return 0
    
    def get_bot_stats(self):
        """Get comprehensive bot statistics"""
        try:
            stats = {}
            
            with self.conn.cursor() as cursor:
                # Total holders
                cursor.execute("SELECT COUNT(*) FROM holders")
                stats['total_holders'] = cursor.fetchone()[0]
                
                # Total snapshots
                cursor.execute("SELECT COUNT(*) FROM snapshots")
                stats['total_snapshots'] = cursor.fetchone()[0]
                
                # Last snapshot date
                cursor.execute("SELECT MAX(snapshot_date) FROM snapshots")
                last_snapshot = cursor.fetchone()[0]
                stats['last_snapshot'] = last_snapshot.strftime('%Y-%m-%d %H:%M') if last_snapshot else 'Never'
                
                # Min USD threshold
                stats['min_usd_threshold'] = self.get_minimum_usd_threshold()
                
                # Database size (approximate)
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                db_size = cursor.fetchone()[0]
                stats['db_size'] = db_size
                
            return stats
            
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {
                'total_holders': 0,
                'total_snapshots': 0,
                'last_snapshot': 'Error',
                'min_usd_threshold': 0.0,
                'db_size': 'Unknown'
            }
    
    def get_first_seen_date(self, wallet_address):
        """Get the first seen date for a wallet address"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT first_seen_date FROM holders WHERE wallet_address = %s
                """, (wallet_address,))
                
                result = cursor.fetchone()
                if result:
                    return result[0]
                return None
                
        except Exception as e:
            logger.error(f"Error getting first seen date for {wallet_address}: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
