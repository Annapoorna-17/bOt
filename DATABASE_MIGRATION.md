# Database Migration Guide

## Problem
New fields (`email`, `address`, `contact_number`) were added to the `User` model, but existing database tables don't have these columns. This causes errors when creating users or companies.

## Solution
The system now includes **automatic database migration** that runs on application startup.

---

## Option 1: Automatic Migration (Recommended)

### Step 1: Start the application
```bash
uvicorn app.main:app --reload
```

The migration will run automatically on startup and display output like:

```
============================================================
DATABASE MIGRATION SCRIPT
============================================================

[1] Checking User table columns...
Adding column: users.email ...
✓ Added column 'users.email'
Adding column: users.address ...
✓ Added column 'users.address'
Adding column: users.contact_number ...
✓ Added column 'users.contact_number'

============================================================
✓ Migration complete: 3 column(s) added
============================================================
```

### Step 2: Update existing users (if any)
If you already have users in the database, they will have empty email addresses. You need to update them:

```sql
-- Connect to your MySQL database
mysql -u root -p rag_db

-- Update existing users with valid emails
UPDATE users SET email = CONCAT(user_code, '@example.com') WHERE email = '';

-- Add unique constraint for email
ALTER TABLE users ADD UNIQUE INDEX idx_users_email (email);
```

---

## Option 2: Manual Migration

If you prefer to run migrations manually:

### Step 1: Run migration script directly
```bash
python -m app.db_migration
```

### Step 2: Verify columns were added
```sql
mysql -u root -p rag_db

DESCRIBE users;
```

You should see:
```
+----------------+--------------+------+-----+---------+----------------+
| Field          | Type         | Null | Key | Default | Extra          |
+----------------+--------------+------+-----+---------+----------------+
| id             | int          | NO   | PRI | NULL    | auto_increment |
| company_id     | int          | NO   | MUL | NULL    |                |
| display_name   | varchar(255) | NO   |     | NULL    |                |
| user_code      | varchar(64)  | NO   | UNI | NULL    |                |
| role           | varchar(32)  | NO   |     | NULL    |                |
| email          | varchar(255) | NO   |     |         |                |  ← NEW
| address        | text         | YES  |     | NULL    |                |  ← NEW
| contact_number | varchar(20)  | YES  |     | NULL    |                |  ← NEW
| api_key        | varchar(128) | NO   | UNI | NULL    |                |
| is_active      | tinyint(1)   | YES  |     | 1       |                |
| created_at     | datetime     | YES  |     | NULL    |                |
+----------------+--------------+------+-----+---------+----------------+
```

---

## Option 3: Drop and Recreate (Development Only)

⚠️ **WARNING: This will DELETE ALL DATA. Only use in development!**

```bash
# Connect to MySQL
mysql -u root -p

# Drop and recreate database
DROP DATABASE IF EXISTS rag_db;
CREATE DATABASE rag_db;
exit

# Restart application - tables will be created with new schema
uvicorn app.main:app --reload
```

---

## Creating Users After Migration

### Updated API Payload
Now when creating users, you MUST include the `email` field:

#### Example 1: Create First Admin (Superadmin)
```bash
curl -X POST http://localhost:8000/superadmin/companies/qwert/admin \
  -H "Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_code": "qwert",
    "display_name": "Admin User",
    "user_code": "qwert-admin",
    "role": "admin",
    "email": "admin@example.com",
    "address": "123 Main St",
    "contact_number": "+1234567890"
  }'
```

#### Example 2: Create Regular User (Admin)
```bash
curl -X POST http://localhost:8000/t/qwert/users \
  -H "X-User-Code: qwert-admin" \
  -H "X-API-Key: <admin_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_code": "qwert",
    "display_name": "John Doe",
    "user_code": "qwert-user1",
    "role": "user",
    "email": "john@example.com",
    "address": "456 Oak Ave",
    "contact_number": "+9876543210"
  }'
```

**Required fields:**
- ✅ `email` - REQUIRED (must be unique across all users)
- ⚠️ `address` - OPTIONAL
- ⚠️ `contact_number` - OPTIONAL

---

## Verification

### Check if migration was successful:
```bash
# Method 1: Check application logs
uvicorn app.main:app --reload
# Look for migration output in console

# Method 2: Query database directly
mysql -u root -p rag_db
SHOW COLUMNS FROM users WHERE Field IN ('email', 'address', 'contact_number');
```

Expected output:
```
+----------------+--------------+------+-----+---------+-------+
| Field          | Type         | Null | Key | Default | Extra |
+----------------+--------------+------+-----+---------+-------+
| email          | varchar(255) | NO   |     |         |       |
| address        | text         | YES  |     | NULL    |       |
| contact_number | varchar(20)  | YES  |     | NULL    |       |
+----------------+--------------+------+-----+---------+-------+
```

---

## Future Migrations

### Adding New Fields
When you add new model fields in the future:

1. **Update the model** (app/models.py)
```python
class MyModel(Base):
    __tablename__ = "my_table"
    # ... existing fields ...
    new_field = Column(String(100), nullable=True)  # NEW
```

2. **Add migration** (app/db_migration.py)
```python
def migrate_database():
    # ... existing migrations ...

    # New migration
    if add_column_if_missing("my_table", "new_field", "VARCHAR(100) NULL"):
        migrations_applied += 1
```

3. **Restart application** - migration runs automatically

---

## Troubleshooting

### Error: "Column 'email' cannot be null"
**Problem**: Database doesn't have the new columns yet.

**Solution**: Run the migration:
```bash
python -m app.db_migration
```

### Error: "Duplicate entry for key 'email'"
**Problem**: Two users have the same email address.

**Solution**: Update duplicate emails:
```sql
UPDATE users SET email = CONCAT(user_code, '@temp.com') WHERE email = '';
```

### Migration doesn't run
**Problem**: Migration script has errors.

**Solution**: Check your database credentials in `.env`:
```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/rag_db
# OR
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
DB_NAME=rag_db
```

---

## Production Deployment

For production environments:

1. **Backup database first**:
```bash
mysqldump -u root -p rag_db > backup_$(date +%Y%m%d).sql
```

2. **Test migration on staging**:
```bash
python -m app.db_migration
```

3. **Deploy to production**:
```bash
# Migration will run automatically on app startup
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. **Verify**:
```bash
curl http://your-server:8000/healthz
# Should return: {"ok": true}
```

---

**Last Updated**: 2025-10-28
