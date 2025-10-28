# Profile Management API - Quick Testing Guide

Step-by-step guide to test the new profile management endpoints.

---

## Prerequisites

1. **Start the server**:
```bash
uvicorn app.main:app --reload
```

2. **Have a test user created** with credentials:
   - Tenant Code: e.g., `qwert`
   - User Code: e.g., `qwert-user1`
   - API Key: (from user creation response)

---

## Test 1: Get Current User Profile

```bash
curl -X GET http://localhost:8000/t/qwert/users/me \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "display_name": "Test User",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "...",
  "email": "user@example.com",
  "address": null,
  "contact_number": null,
  "profile_image": null
}
```

✅ **Pass**: User profile returned with `profile_image: null`

---

## Test 2: Update Profile Information

```bash
curl -X PUT http://localhost:8000/t/qwert/users/me \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "Updated Name",
    "address": "123 Test Street",
    "contact_number": "+1234567890"
  }'
```

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "display_name": "Updated Name",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "...",
  "email": "user@example.com",
  "address": "123 Test Street",
  "contact_number": "+1234567890",
  "profile_image": null
}
```

✅ **Pass**: Profile updated with new values

---

## Test 3: Upload Profile Image

### Using a local image file:

```bash
# Replace /path/to/image.jpg with actual path to a JPG/PNG image
curl -X POST http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -F "file=@/path/to/image.jpg"
```

### Create a test image (Windows):

```powershell
# Using PowerShell to download a test image
Invoke-WebRequest -Uri "https://via.placeholder.com/500" -OutFile "test-profile.jpg"

# Then upload it
curl -X POST http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -F "file=@test-profile.jpg"
```

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "display_name": "Updated Name",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "...",
  "email": "user@example.com",
  "address": "123 Test Street",
  "contact_number": "+1234567890",
  "profile_image": "qwert-user1_a1b2c3d4e5f6.jpg"
}
```

✅ **Pass**:
- Profile image uploaded
- Filename follows pattern: `{user_code}_{unique_id}.{ext}`
- File exists in `profile_images/` directory

### Verify file was created:

```bash
# Windows
dir profile_images

# Should show: qwert-user1_XXXXXXXXXXXX.jpg
```

---

## Test 4: Update Profile Image (Replace)

Upload a different image to replace the existing one:

```bash
curl -X POST http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -F "file=@another-image.png"
```

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "display_name": "Updated Name",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "...",
  "email": "user@example.com",
  "address": "123 Test Street",
  "contact_number": "+1234567890",
  "profile_image": "qwert-user1_f9e8d7c6b5a4.png"
}
```

✅ **Pass**:
- New filename returned
- Old image file deleted from disk
- New image saved

---

## Test 5: Delete Profile Image

```bash
curl -X DELETE http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "display_name": "Updated Name",
  "user_code": "qwert-user1",
  "role": "user",
  "api_key": "...",
  "email": "user@example.com",
  "address": "123 Test Street",
  "contact_number": "+1234567890",
  "profile_image": null
}
```

✅ **Pass**:
- `profile_image` set to `null`
- Physical file deleted from disk

---

## Test 6: Error Cases

### 6A: Upload Invalid File Type

```bash
# Try to upload a text file
echo "This is not an image" > fake.txt

curl -X POST http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -F "file=@fake.txt"
```

**Expected Response** (400 Bad Request):
```json
{
  "detail": "Invalid file type. Allowed types: .jpg, .jpeg, .png, .gif, .webp"
}
```

✅ **Pass**: Rejected with appropriate error

---

### 6B: Update Email to Duplicate

Assuming another user exists with email `existing@example.com`:

```bash
curl -X PUT http://localhost:8000/t/qwert/users/me \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "existing@example.com"
  }'
```

**Expected Response** (409 Conflict):
```json
{
  "detail": "Email already in use by another user"
}
```

✅ **Pass**: Email uniqueness enforced

---

### 6C: Delete Non-Existent Image

If profile image is already null:

```bash
curl -X DELETE http://localhost:8000/t/qwert/users/me/profile-image \
  -H "X-User-Code: qwert-user1" \
  -H "X-API-Key: YOUR_API_KEY_HERE"
```

**Expected Response** (404 Not Found):
```json
{
  "detail": "No profile image to delete"
}
```

✅ **Pass**: Appropriate error for missing image

---

## Test 7: Using Postman/Insomnia

### 7A: Setup

1. **Create Environment Variables**:
   - `BASE_URL`: `http://localhost:8000`
   - `TENANT_CODE`: `qwert`
   - `USER_CODE`: `qwert-user1`
   - `API_KEY`: `your_actual_api_key`

2. **Set Headers** (for all requests):
   - `X-User-Code`: `{{USER_CODE}}`
   - `X-API-Key`: `{{API_KEY}}`

---

### 7B: Get Profile

- **Method**: `GET`
- **URL**: `{{BASE_URL}}/t/{{TENANT_CODE}}/users/me`
- **Headers**: (set above)

---

### 7C: Update Profile

- **Method**: `PUT`
- **URL**: `{{BASE_URL}}/t/{{TENANT_CODE}}/users/me`
- **Headers**: Add `Content-Type: application/json`
- **Body** (JSON):
```json
{
  "display_name": "New Name",
  "address": "New Address"
}
```

---

### 7D: Upload Image

- **Method**: `POST`
- **URL**: `{{BASE_URL}}/t/{{TENANT_CODE}}/users/me/profile-image`
- **Headers**: (set above, no Content-Type needed)
- **Body**:
  - Type: `form-data`
  - Key: `file`
  - Type: `File`
  - Value: Select image file

---

## Verification Checklist

After running all tests, verify:

- [ ] User profile can be retrieved
- [ ] Profile information can be updated (partial updates work)
- [ ] Email uniqueness is enforced
- [ ] Profile images upload successfully
- [ ] Image files are stored in `profile_images/` directory
- [ ] Replacing image deletes old file
- [ ] Profile images can be deleted
- [ ] Deleting image removes physical file
- [ ] Invalid file types are rejected
- [ ] File size limits are enforced (try uploading >5MB file)
- [ ] `profile_image` field appears in all user responses

---

## Common Issues

### Issue: "Unknown column 'users.profile_image'"

**Solution**: Run the migration:
```bash
python -m app.db_migration
```

---

### Issue: Image uploaded but file not found

**Solution**: Check the `profile_images/` directory exists:
```bash
# Windows
mkdir profile_images

# Then restart the server
```

---

### Issue: "Invalid image file" error

**Solution**: Ensure you're uploading actual image files (JPG, PNG, etc.), not renamed text files.

---

## Next Steps

Once all tests pass:

1. ✅ Profile management API is working
2. 🎨 Integrate with frontend
3. 📸 Add profile image serving endpoint (optional)
4. 🔒 Consider adding image moderation (optional)

---

**Last Updated**: 2025-10-28
