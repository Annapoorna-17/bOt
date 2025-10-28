# User Profile Management API

Complete guide for managing user profiles including profile information updates and profile image uploads.

---

## Overview

Users can now:
- ✅ View their profile information
- ✅ Update profile details (name, email, address, contact number)
- ✅ Upload a profile image (JPG, PNG, GIF, WEBP)
- ✅ Update/replace their profile image
- ✅ Delete their profile image

---

## Database Schema

### User Model - New Fields

```python
class User(Base):
    # ... existing fields ...

    # Profile fields
    email: str              # Required, unique
    address: str           # Optional
    contact_number: str    # Optional
    profile_image: str     # Optional - stores filename
```

---

## API Endpoints

### Header-Based Routes (Original)

Base path: `/users`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Get current user profile |
| PUT | `/users/me` | Update profile information |
| POST | `/users/me/profile-image` | Upload/update profile image |
| DELETE | `/users/me/profile-image` | Delete profile image |

**Required Headers:**
- `X-Tenant-Code`: Your company's tenant code
- `X-User-Code`: Your user code
- `X-API-Key`: Your API key

---

### Tenant-Scoped Routes (Recommended)

Base path: `/t/{tenant_code}/users`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/t/{tenant_code}/users/me` | Get current user profile |
| PUT | `/t/{tenant_code}/users/me` | Update profile information |
| POST | `/t/{tenant_code}/users/me/profile-image` | Upload/update profile image |
| DELETE | `/t/{tenant_code}/users/me/profile-image` | Delete profile image |

**Required Headers:**
- `X-User-Code`: Your user code
- `X-API-Key`: Your API key

---

## 1. Get User Profile

Retrieve the authenticated user's complete profile information.

### Request

```bash
# Header-based
curl -X GET http://localhost:8000/users/me \
  -H "X-Tenant-Code: qwert" \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: <your_api_key>"

# Tenant-scoped (recommended)
curl -X GET http://localhost:8000/t/qwert/users/me \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: <your_api_key>"
```

### Response (200 OK)

```json
{
  "id": 1,
  "display_name": "John Doe",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "your_api_key_here",
  "email": "john@example.com",
  "address": "123 Main St, City, State",
  "contact_number": "+1234567890",
  "profile_image": "qwert-user1_a1b2c3d4e5f6.jpg"
}
```

---

## 2. Update Profile Information

Update user profile fields. All fields are optional - only send the fields you want to update.

### Request

```bash
# Tenant-scoped (recommended)
curl -X PUT http://localhost:8000/t/qwert/users/me \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Smith",
    "email": "john.smith@example.com",
    "address": "456 Oak Avenue, New City",
    "contact_number": "+9876543210"
  }'
```

### Request Body Schema

```json
{
  "display_name": "string (optional)",
  "email": "string (optional, must be unique)",
  "address": "string (optional)",
  "contact_number": "string (optional)"
}
```

### Partial Update Examples

**Update only name:**
```json
{
  "display_name": "Jane Doe"
}
```

**Update only email:**
```json
{
  "email": "newemail@example.com"
}
```

**Update multiple fields:**
```json
{
  "display_name": "Jane Doe",
  "contact_number": "+1111111111"
}
```

### Response (200 OK)

Returns the updated user object with all current values.

```json
{
  "id": 1,
  "display_name": "John Smith",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "your_api_key_here",
  "email": "john.smith@example.com",
  "address": "456 Oak Avenue, New City",
  "contact_number": "+9876543210",
  "profile_image": "qwert-user1_a1b2c3d4e5f6.jpg"
}
```

### Error Responses

**409 Conflict** - Email already in use
```json
{
  "detail": "Email already in use by another user"
}
```

---

## 3. Upload Profile Image

Upload or replace the user's profile image. Automatically replaces the old image if one exists.

### Image Requirements

- **Formats**: JPG, JPEG, PNG, GIF, WEBP
- **Max Size**: 5 MB
- **Auto-resize**: Images larger than 1024x1024 are automatically resized
- **Optimization**: Images are compressed (quality 85%) to save space

### Request

```bash
# Tenant-scoped (recommended)
curl -X POST http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: <your_api_key>" \
  -F "file=@/path/to/profile-picture.jpg"
```

### Using JavaScript/Fetch

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/t/qwert/users/me/profile-image', {
  method: 'POST',
  headers: {
    'X-User-Code': 'qwert-user1',
    'X-API-Key': 'your_api_key_here'
  },
  body: formData
});

const user = await response.json();
console.log('Profile image uploaded:', user.profile_image);
```

### Response (200 OK)

Returns the updated user object with the new profile_image filename.

```json
{
  "id": 1,
  "display_name": "John Doe",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "your_api_key_here",
  "email": "john@example.com",
  "address": "123 Main St",
  "contact_number": "+1234567890",
  "profile_image": "qwert-user1_f8e7d6c5b4a3.jpg"
}
```

### Error Responses

**400 Bad Request** - Invalid file type
```json
{
  "detail": "Invalid file type. Allowed types: .jpg, .jpeg, .png, .gif, .webp"
}
```

**400 Bad Request** - File too large
```json
{
  "detail": "File too large. Maximum size: 5MB"
}
```

**400 Bad Request** - Invalid image
```json
{
  "detail": "Invalid image file"
}
```

---

## 4. Delete Profile Image

Remove the user's profile image. Sets `profile_image` to `null` and deletes the physical file.

### Request

```bash
# Tenant-scoped (recommended)
curl -X DELETE http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: <your_api_key>"
```

### Response (200 OK)

Returns the user object with `profile_image` set to `null`.

```json
{
  "id": 1,
  "display_name": "John Doe",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "your_api_key_here",
  "email": "john@example.com",
  "address": "123 Main St",
  "contact_number": "+1234567890",
  "profile_image": null
}
```

### Error Responses

**404 Not Found** - No profile image exists
```json
{
  "detail": "No profile image to delete"
}
```

---

## File Storage

### Storage Location

Profile images are stored in: `profile_images/`

### Filename Format

```
{user_code}_{unique_id}{extension}
```

**Example:**
- User code: `qwert-user1`
- Unique ID: `a1b2c3d4e5f6` (12-char random)
- Extension: `.jpg`
- **Result**: `qwert-user1_a1b2c3d4e5f6.jpg`

### File Management

- **Upload**: Old image is automatically deleted before saving new one
- **Update**: Same as upload - replaces existing image
- **Delete**: Physical file removed from disk and database field set to `null`

---

## Image Processing

### Automatic Optimizations

1. **Format Validation**: Only allows JPG, PNG, GIF, WEBP
2. **Size Check**: Rejects files over 5MB
3. **Image Verification**: Uses PIL to verify file is actually an image
4. **Auto-Resize**: Images > 1024x1024 are resized maintaining aspect ratio
5. **Format Conversion**: RGBA/transparency converted to RGB (white background)
6. **Compression**: Saved with 85% quality for optimal size/quality balance

### Example Processing

**Original Image:**
- Size: 3000×2000 px
- Format: PNG with transparency
- File size: 4.5 MB

**After Processing:**
- Size: 1024×683 px (aspect ratio preserved)
- Format: JPEG
- File size: ~150 KB
- Background: White (transparency removed)

---

## Frontend Integration Guide

### React Example - Complete Profile Page

```javascript
import React, { useState, useEffect } from 'react';

function UserProfile() {
  const [user, setUser] = useState(null);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({});

  const tenantCode = 'qwert';
  const userCode = 'qwert-user1';
  const apiKey = 'your_api_key_here';

  const headers = {
    'X-User-Code': userCode,
    'X-API-Key': apiKey
  };

  // Load user profile
  useEffect(() => {
    fetch(`http://localhost:8000/t/${tenantCode}/users/me`, { headers })
      .then(res => res.json())
      .then(data => {
        setUser(data);
        setFormData({
          display_name: data.display_name,
          email: data.email,
          address: data.address || '',
          contact_number: data.contact_number || ''
        });
      });
  }, []);

  // Update profile
  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    const response = await fetch(`http://localhost:8000/t/${tenantCode}/users/me`, {
      method: 'PUT',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    const updated = await response.json();
    setUser(updated);
    setEditing(false);
  };

  // Upload profile image
  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`http://localhost:8000/t/${tenantCode}/users/me/profile-image`, {
      method: 'POST',
      headers,
      body: formData
    });

    const updated = await response.json();
    setUser(updated);
  };

  // Delete profile image
  const handleDeleteImage = async () => {
    const response = await fetch(`http://localhost:8000/t/${tenantCode}/users/me/profile-image`, {
      method: 'DELETE',
      headers
    });
    const updated = await response.json();
    setUser(updated);
  };

  if (!user) return <div>Loading...</div>;

  return (
    <div className="profile-page">
      <h1>My Profile</h1>

      {/* Profile Image Section */}
      <div className="profile-image-section">
        {user.profile_image ? (
          <div>
            <img
              src={`/profile_images/${user.profile_image}`}
              alt="Profile"
              className="profile-image"
            />
            <button onClick={handleDeleteImage}>Remove Image</button>
          </div>
        ) : (
          <div className="no-image">No profile image</div>
        )}
        <input
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          onChange={handleImageUpload}
        />
      </div>

      {/* Profile Information Section */}
      {editing ? (
        <form onSubmit={handleUpdateProfile}>
          <input
            type="text"
            value={formData.display_name}
            onChange={(e) => setFormData({...formData, display_name: e.target.value})}
            placeholder="Display Name"
          />
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({...formData, email: e.target.value})}
            placeholder="Email"
          />
          <input
            type="text"
            value={formData.address}
            onChange={(e) => setFormData({...formData, address: e.target.value})}
            placeholder="Address"
          />
          <input
            type="tel"
            value={formData.contact_number}
            onChange={(e) => setFormData({...formData, contact_number: e.target.value})}
            placeholder="Contact Number"
          />
          <button type="submit">Save Changes</button>
          <button type="button" onClick={() => setEditing(false)}>Cancel</button>
        </form>
      ) : (
        <div className="profile-info">
          <p><strong>Name:</strong> {user.display_name}</p>
          <p><strong>Email:</strong> {user.email}</p>
          <p><strong>Role:</strong> {user.role}</p>
          <p><strong>Address:</strong> {user.address || 'Not provided'}</p>
          <p><strong>Phone:</strong> {user.contact_number || 'Not provided'}</p>
          <button onClick={() => setEditing(true)}>Edit Profile</button>
        </div>
      )}
    </div>
  );
}

export default UserProfile;
```

---

## Security Considerations

### Authentication
- All endpoints require valid API key
- Users can only update their own profile
- Cross-tenant access is blocked

### Image Validation
- File extension check
- File size limit (5MB)
- PIL verification (ensures file is actually an image)
- Automatic format conversion (prevents malicious files)

### File Storage
- Unique filenames prevent overwrites
- User code in filename for easy identification
- Old images automatically deleted on replacement

---

## Migration Required

Before using these endpoints, run the database migration:

```bash
# The migration will run automatically on app startup
uvicorn app.main:app --reload

# Or run manually
python -m app.db_migration
```

This adds the `profile_image` column to the `users` table.

---

## Testing Checklist

- [ ] Get user profile (no image)
- [ ] Upload profile image (JPG)
- [ ] Get user profile (with image)
- [ ] Update profile image (replace with PNG)
- [ ] Update profile info (name, email)
- [ ] Verify email uniqueness (try duplicate email)
- [ ] Delete profile image
- [ ] Try uploading invalid file (PDF, EXE)
- [ ] Try uploading file > 5MB
- [ ] Verify old image deleted after replacement

---

**Last Updated**: 2025-10-28
