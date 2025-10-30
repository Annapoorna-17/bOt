"""
Database migration helper for adding new columns to existing tables.

This script checks for missing columns and adds them automatically.
Run this before starting the app if you've added new model fields.
"""
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "") 
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "bott")
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)


def get_existing_columns(table_name: str) -> set:
    """Get set of existing column names for a table."""
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return set()
    columns = inspector.get_columns(table_name)
    return {col['name'] for col in columns}


def add_column_if_missing(table_name: str, column_name: str, column_definition: str):
    """Add a column to a table if it doesn't exist."""
    existing_cols = get_existing_columns(table_name)

    if column_name in existing_cols:
        print(f"[OK] Column '{table_name}.{column_name}' already exists")
        return False

    try:
        with engine.connect() as conn:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            print(f"Adding column: {table_name}.{column_name} ...")
            conn.execute(text(sql))
            conn.commit()
            print(f"[OK] Added column '{table_name}.{column_name}'")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to add column '{table_name}.{column_name}': {e}")
        return False


def modify_column_if_needed(table_name: str, column_name: str, new_definition: str):
    """Modify a column definition if it exists."""
    existing_cols = get_existing_columns(table_name)

    if column_name not in existing_cols:
        print(f"[SKIP] Column '{table_name}.{column_name}' does not exist")
        return False

    try:
        with engine.connect() as conn:
            sql = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {new_definition}"
            print(f"Modifying column: {table_name}.{column_name} ...")
            conn.execute(text(sql))
            conn.commit()
            print(f"[OK] Modified column '{table_name}.{column_name}'")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to modify column '{table_name}.{column_name}': {e}")
        return False


def migrate_database():
    """Run all migrations to bring database schema up to date."""
    print("=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("=" * 60)

    migrations_applied = 0

    # Migration 1: Add company fields (email, phone, website, address)
    print("\n[1] Checking Company table columns...")

    if add_column_if_missing("companies", "email", "VARCHAR(255) NULL"):
        migrations_applied += 1

    if add_column_if_missing("companies", "phone", "VARCHAR(50) NULL"):
        migrations_applied += 1

    if add_column_if_missing("companies", "website", "VARCHAR(255) NULL"):
        migrations_applied += 1

    if add_column_if_missing("companies", "address", "VARCHAR(255) NULL"):
        migrations_applied += 1
    # --- NEW FIELDS FOR COMPANY ---
    if add_column_if_missing("companies", "city", "VARCHAR(100) NULL"):
        migrations_applied += 1
    if add_column_if_missing("companies", "state", "VARCHAR(100) NULL"):
        migrations_applied += 1
    if add_column_if_missing("companies", "country", "VARCHAR(100) NULL"):
        migrations_applied += 1
    # --- END NEW FIELDS ---

    if add_column_if_missing("companies", "widget_key", "VARCHAR(128) NULL UNIQUE"):
        migrations_applied += 1

    # Migration 2: Add user fields (email, address, contact_number)
    print("\n[2] Checking User table columns...")

    # Email is required, so use empty string as default for existing rows
    if add_column_if_missing("users", "email", "VARCHAR(255) NOT NULL DEFAULT ''"):
        migrations_applied += 1
        # After adding with default, we should make unique constraint
        # But for existing data, we need to update first
        print("  [WARNING] NOTE: You need to update existing users with valid emails!")
        print("  [WARNING] Then run: ALTER TABLE users ADD UNIQUE INDEX idx_users_email (email);")

    if add_column_if_missing("users", "firstname", "VARCHAR(100) NULL"):
        migrations_applied += 1
    if add_column_if_missing("users", "lastname", "VARCHAR(100) NULL"):
        migrations_applied += 1    

    if add_column_if_missing("users", "address", "TEXT NULL"):
        migrations_applied += 1
    if add_column_if_missing("users", "city", "VARCHAR(100) NULL"):
        migrations_applied += 1
    if add_column_if_missing("users", "state", "VARCHAR(100) NULL"):
        migrations_applied += 1
    if add_column_if_missing("users", "country", "VARCHAR(100) NULL"):
        migrations_applied += 1

    if add_column_if_missing("users", "contact_number", "VARCHAR(20) NULL"):
        migrations_applied += 1

    if add_column_if_missing("users", "profile_image", "VARCHAR(512) NULL"):
        migrations_applied += 1

    if add_column_if_missing("users", "hashed_password", "VARCHAR(255) NULL"):
        migrations_applied += 1

    # Migration 3: Make api_key nullable (for JWT users who don't have API keys)
    print("\n[3] Ensuring api_key is nullable for JWT users...")
    if modify_column_if_needed("users", "api_key", "VARCHAR(128) NULL"):
        migrations_applied += 1

    # Migration 4: Add CASCADE DELETE to foreign keys
    print("\n[4] Updating foreign keys with CASCADE DELETE...")
    try:
        with engine.connect() as conn:
            # Get existing foreign key names
            inspector = inspect(engine)

            # Users table - company_id foreign key
            try:
                print("  Updating users.company_id foreign key...")
                fk_info = inspector.get_foreign_keys("users")
                users_company_fk = next((fk['name'] for fk in fk_info if 'company_id' in fk['constrained_columns']), None)

                if users_company_fk:
                    conn.execute(text(f"ALTER TABLE users DROP FOREIGN KEY {users_company_fk}"))
                    conn.execute(text(
                        "ALTER TABLE users ADD CONSTRAINT users_company_fk "
                        "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE"
                    ))
                    conn.commit()
                    print(f"  [OK] Updated users.company_id foreign key with CASCADE DELETE")
                    migrations_applied += 1
                else:
                    print(f"  [SKIP] No foreign key found on users.company_id")
            except Exception as e:
                print(f"  [ERROR] Failed to update users.company_id: {e}")

            # Documents table - company_id and uploader_id foreign keys
            try:
                print("  Updating documents foreign keys...")
                fk_info = inspector.get_foreign_keys("documents")

                docs_company_fk = next((fk['name'] for fk in fk_info if 'company_id' in fk['constrained_columns']), None)
                if docs_company_fk:
                    conn.execute(text(f"ALTER TABLE documents DROP FOREIGN KEY {docs_company_fk}"))
                    conn.execute(text(
                        "ALTER TABLE documents ADD CONSTRAINT documents_company_fk "
                        "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE"
                    ))
                    migrations_applied += 1

                docs_uploader_fk = next((fk['name'] for fk in fk_info if 'uploader_id' in fk['constrained_columns']), None)
                if docs_uploader_fk:
                    conn.execute(text(f"ALTER TABLE documents DROP FOREIGN KEY {docs_uploader_fk}"))
                    conn.execute(text(
                        "ALTER TABLE documents ADD CONSTRAINT documents_uploader_fk "
                        "FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE"
                    ))
                    migrations_applied += 1

                conn.commit()
                print(f"  [OK] Updated documents foreign keys with CASCADE DELETE")
            except Exception as e:
                print(f"  [ERROR] Failed to update documents foreign keys: {e}")

            # Websites table - company_id and uploader_id foreign keys
            try:
                print("  Updating websites foreign keys...")
                fk_info = inspector.get_foreign_keys("websites")

                web_company_fk = next((fk['name'] for fk in fk_info if 'company_id' in fk['constrained_columns']), None)
                if web_company_fk:
                    conn.execute(text(f"ALTER TABLE websites DROP FOREIGN KEY {web_company_fk}"))
                    conn.execute(text(
                        "ALTER TABLE websites ADD CONSTRAINT websites_company_fk "
                        "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE"
                    ))
                    migrations_applied += 1

                web_uploader_fk = next((fk['name'] for fk in fk_info if 'uploader_id' in fk['constrained_columns']), None)
                if web_uploader_fk:
                    conn.execute(text(f"ALTER TABLE websites DROP FOREIGN KEY {web_uploader_fk}"))
                    conn.execute(text(
                        "ALTER TABLE websites ADD CONSTRAINT websites_uploader_fk "
                        "FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE"
                    ))
                    migrations_applied += 1

                conn.commit()
                print(f"  [OK] Updated websites foreign keys with CASCADE DELETE")
            except Exception as e:
                print(f"  [ERROR] Failed to update websites foreign keys: {e}")

    except Exception as e:
        print(f"  [ERROR] CASCADE DELETE migration failed: {e}")

    print("\n" + "=" * 60)
    if migrations_applied > 0:
        print(f"[SUCCESS] Migration complete: {migrations_applied} change(s) applied")
    else:
        print("[SUCCESS] Database schema is up to date")
    print("=" * 60)


if __name__ == "__main__":
    migrate_database()
