"""
Migration script to fix User table schema.
Adds the missing preferred_region column and migrates data from old columns.
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def migrate_user_schema():
    """Add preferred_region column and migrate data from old columns"""
    conn = sqlite3.connect('products.db')
    cursor = conn.cursor()
    
    try:
        print("[*] Starting User table schema migration...")
        
        # Check if preferred_region column already exists
        cursor.execute("PRAGMA table_info(users);")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'preferred_region' not in columns:
            print("  [+] Adding preferred_region column...")
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN preferred_region VARCHAR(10) DEFAULT 'en-ua'
            """)
            print("  [OK] Column added")
            
            # Migrate data from preferred_country to preferred_region
            print("  [*] Migrating data from preferred_country to preferred_region...")
            
            # Mapping old country codes to new region codes
            country_to_region = {
                'UA': 'en-ua',
                'TR': 'en-tr',
                'IN': 'en-in',
                'Ukraine': 'en-ua',
                'Turkey': 'en-tr',
                'India': 'en-in'
            }
            
            # Get all users
            cursor.execute("SELECT id, preferred_country FROM users")
            users = cursor.fetchall()
            
            for user_id, preferred_country in users:
                if preferred_country:
                    # Convert old format to new format
                    region = country_to_region.get(preferred_country, 'en-ua')
                    cursor.execute(
                        "UPDATE users SET preferred_region = ? WHERE id = ?",
                        (region, user_id)
                    )
                    print(f"    -> User {user_id}: {preferred_country} -> {region}")
            
            conn.commit()
            print("  [OK] Data migration completed")
        else:
            print("  [INFO] preferred_region column already exists")
        
        # Display updated schema
        print("\n[*] Updated User table schema:")
        cursor.execute("PRAGMA table_info(users);")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else 'NULL'}")
        
        # Display sample data
        print("\n[*] Sample user data:")
        cursor.execute("SELECT id, telegram_id, username, preferred_region, preferred_country FROM users LIMIT 3")
        users = cursor.fetchall()
        for user in users:
            print(f"  -> User ID: {user[0]}, Telegram: {user[1]}, Username: {user[2]}, Region: {user[3]}, Old Country: {user[4]}")
        
        print("\n[SUCCESS] Migration completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_user_schema()

