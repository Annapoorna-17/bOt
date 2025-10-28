# 🚀 Multi-Tenant RAG API Guide

**Simplified JWT-Only Authentication** - Clean, modern, and user-friendly!

---

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Superadmin Setup](#superadmin-setup)
5. [Common Workflows](#common-workflows)

---

## Quick Start

### Superadmin Credentials
```
Bearer Token: B946C6F2747914D24C1F6C74F5AB5291
OR
Basic Auth: username=stixis, password=password
```

### Base URL
```
http://localhost:8000
```

### Documentation
```
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
```

---

## Authentication

**All endpoints (except superadmin and auth) require a Bearer token:**

```bash
Authorization: Bearer <your_access_token>
```

### How to Get a Token

1. **Register** (if you don't have an account):
```bash
POST /auth/register
{
  "tenant_code": "qwert",
  "display_name": "John Doe",
  "user_code": "qwert-john",
  "role": "user",
  "email": "john@example.com",
  "password": "SecurePassword123",
  "address": "123 Main St",
  "contact_number": "+1234567890"
}
```

2. **Login** to get your token:
```bash
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=john@example.com&password=SecurePassword123
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUz...",
  "refresh_token": "eyJhbGciOiJIUz...",
  "token_type": "bearer"
}
```

3. **Use the token** in all requests:
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUz..." \
  http://localhost:8000/users/me
```

---

## API Endpoints

### 🔐 Authentication (`/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and get access token |
| POST | `/auth/refresh-token` | Refresh your access token |
| POST | `/auth/request-password-reset` | Request password reset |
| POST | `/auth/reset-password` | Reset password with token |

---

### 👤 User Management (`/users`)

| Method | Endpoint | Description | Admin Only |
|--------|----------|-------------|------------|
| POST | `/users` | Create a new user | ✅ |
| GET | `/users` | List all users in your tenant | |
| GET | `/users/me` | Get your profile | |
| PUT | `/users/me` | Update your profile | |
| POST | `/users/me/image` | Upload profile image | |
| DELETE | `/users/me/image` | Delete profile image | |

**Profile Image URL:**
```
http://localhost:8000/profile-images/{filename}
```

---

### 📄 Document Management (`/documents`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload a PDF document |
| GET | `/documents` | List documents (query param: `my_docs_only=true`) |
| DELETE | `/documents/{id}` | Delete a document |

**Upload Example:**
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"
```

---

### 🌐 Website Scraping (`/websites`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/websites/scrape` | Scrape and index a website |
| GET | `/websites` | List scraped websites (query param: `my_websites_only=true`) |
| DELETE | `/websites/{id}` | Delete a website |

**Scrape Example:**
```bash
curl -X POST http://localhost:8000/websites/scrape \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

---

### 🔍 Query / RAG (`/query`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Ask questions about your documents and websites |

**Query Example:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "top_k": 5,
    "user_filter": false
  }'
```

**Response:**
```json
{
  "answer": "The document discusses...",
  "sources": [
    "qwert_user1_abc123.pdf",
    "https://example.com"
  ]
}
```

---

## Superadmin Setup

### 1️⃣ Create a Company/Tenant

```bash
POST /superadmin/companies
Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291

{
  "name": "Acme Corp",
  "tenant_code": "acme",
  "email": "admin@acme.com",
  "phone": "+1234567890",
  "address": "123 Business St"
}
```

### 2️⃣ Create First Admin User

```bash
POST /superadmin/companies/acme/admin
Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291

{
  "tenant_code": "acme",
  "display_name": "Admin User",
  "user_code": "acme-admin",
  "role": "admin",
  "email": "admin@acme.com",
  "password": "SecurePassword123"
}
```

### 3️⃣ Admin Logs In

```bash
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin@acme.com&password=SecurePassword123
```

### 4️⃣ Admin Creates Additional Users

```bash
POST /users
Authorization: Bearer {admin_token}

{
  "tenant_code": "acme",
  "display_name": "Regular User",
  "user_code": "acme-user1",
  "role": "user",
  "email": "user@acme.com",
  "password": "UserPassword123"
}
```

---

## Common Workflows

### 📝 Upload and Query a Document

```bash
# 1. Login
curl -X POST http://localhost:8000/auth/login \
  -d "username=user@acme.com&password=UserPassword123"

# Save the access_token from response

# 2. Upload document
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@mydoc.pdf"

# 3. Query the document
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the document", "top_k": 5}'
```

### 🌍 Scrape and Query a Website

```bash
# 1. Scrape website
curl -X POST http://localhost:8000/websites/scrape \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org"}'

# 2. Query the website content
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I use async/await?", "top_k": 5}'
```

### 👤 Manage Your Profile

```bash
# Get profile
GET /users/me

# Update profile
PUT /users/me
{
  "display_name": "New Name",
  "address": "New Address"
}

# Upload profile image
POST /users/me/image
[multipart/form-data with file]

# View profile image
GET /profile-images/{filename}
```

---

## 🔒 Security Features

- ✅ **JWT Authentication** - Secure token-based auth
- ✅ **Password Hashing** - bcrypt_sha256 for strong security
- ✅ **Token Expiration** - Access tokens expire in 30 minutes
- ✅ **Refresh Tokens** - Long-lived tokens (7 days) for seamless re-auth
- ✅ **Multi-Tenant Isolation** - Strict data separation between tenants
- ✅ **Role-Based Access** - Admin and user roles with different permissions

---

## 🎯 Key Improvements

**Before (Confusing):**
- Multiple auth systems (API keys + JWT)
- Duplicate endpoints (`/users/*`, `/users/jwt/*`, `/t/{tenant}/*`)
- Required 3 headers for authentication
- Mixed authentication methods

**After (Simple):**
- ✅ Single JWT authentication
- ✅ Clean, RESTful endpoints
- ✅ One Bearer token for everything
- ✅ Modern, industry-standard security
- ✅ Easy to understand and use

---

## 💡 Pro Tips

1. **Token Storage**: Store access tokens securely (localStorage/sessionStorage for web apps)
2. **Refresh Flow**: Use refresh tokens to get new access tokens without re-login
3. **Error Handling**: Check for 401 (Unauthorized) to trigger re-authentication
4. **Swagger UI**: Use `/docs` to test all endpoints interactively
5. **Profile Images**: Files are resized to max 1024x1024 and optimized automatically

---

## 🆘 Need Help?

- 📖 API Docs: http://localhost:8000/docs
- 🔧 Health Check: http://localhost:8000/healthz
- 📧 Superadmin: Use token `B946C6F2747914D24C1F6C74F5AB5291`

---

**Happy Coding! 🚀**
