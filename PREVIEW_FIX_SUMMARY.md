# Document Preview Fix Summary

## Problem
Document preview endpoints were failing with "Document file not found on server" error because files were stored in two different directories:
- **`uploaded_pdfs/`** - Contains PDF files
- **`uploaded_documents/`** - Contains other document types (DOCX, XLSX, PPTX, TXT, etc.)

The preview endpoints were only checking `uploaded_documents/`, causing PDFs to not be found.

## Solution
Updated the document preview system to check both directories automatically.

## Changes Made

### 1. Added Second Upload Directory (`app/routers/documents.py:20`)
```python
UPLOAD_DIR = os.path.abspath("uploaded_documents")
UPLOAD_DIR_PDFS = os.path.abspath("uploaded_pdfs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR_PDFS, exist_ok=True)
```

### 2. Created Helper Function (`app/routers/documents.py:34-50`)
```python
def get_document_path(filename: str) -> str:
    """
    Find the document file path by checking both upload directories.
    Returns the absolute path if found, None otherwise.
    """
    # Check uploaded_documents directory first
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(path):
        return path

    # Check uploaded_pdfs directory for PDFs
    path_pdf = os.path.join(UPLOAD_DIR_PDFS, filename)
    if os.path.exists(path_pdf):
        return path_pdf

    # File not found in either directory
    return None
```

### 3. Updated Normal User Preview Endpoint (`app/routers/documents.py:222`)
- Now uses `get_document_path()` to find files in correct directory
- Added debug logging showing both directories being checked
- Enhanced error message

### 4. Updated Superadmin Preview Endpoint (`app/routers/documents.py:305`)
- Now uses `get_document_path()` to find files in correct directory
- Added debug logging showing both directories being checked
- Enhanced error message

### 5. Updated List Documents Endpoint (`app/routers/documents.py:142`)
- Returns correct filepath using `get_document_path()`
- Works for both normal users and superadmin

### 6. Updated Delete Document Endpoint (`app/routers/documents.py:187`)
- Now deletes from correct directory using `get_document_path()`
- Works for files in both directories

## Endpoints Fixed

✅ **GET /documents/{document_id}/preview** - Normal user preview
✅ **GET /documents/superadmin/{document_id}/preview** - Superadmin preview
✅ **GET /documents** - List documents (correct filepath)
✅ **GET /documents/superadmin/all** - List all documents (correct filepath)
✅ **DELETE /documents/{document_id}** - Delete from correct directory

## Testing

### Restart Your Server
```bash
# Stop the server (Ctrl+C)
# Restart it
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Test Preview Endpoints

**For PDFs (in uploaded_pdfs/):**
```bash
# Superadmin preview
curl -X GET http://localhost:8000/documents/superadmin/1/preview \
  -H "Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291" \
  --output test.pdf

# Normal user preview (requires JWT token)
curl -X GET http://localhost:8000/documents/1/preview \
  -H "Authorization: Bearer your-jwt-token" \
  --output test.pdf
```

**For other documents (in uploaded_documents/):**
```bash
# Superadmin preview
curl -X GET http://localhost:8000/documents/superadmin/2/preview \
  -H "Authorization: Bearer B946C6F2747914D24C1F6C74F5AB5291" \
  --output test.docx
```

### Debug Logging

When you make a preview request, check your server console for debug output:

```
DEBUG - Preview request (superadmin):
  Document ID: 1
  Filename: hjkl_emp1_113207df.pdf
  UPLOAD_DIR: W:\bOt\uploaded_documents
  UPLOAD_DIR_PDFS: W:\bOt\uploaded_pdfs
  Found path: W:\bOt\uploaded_pdfs\hjkl_emp1_113207df.pdf
```

This will show:
- Which document is being requested
- Both directories being checked
- The actual path where the file was found

## Benefits

1. ✅ **Automatic Directory Detection** - No need to specify which directory
2. ✅ **Backward Compatible** - Works with existing code
3. ✅ **Better Error Messages** - Tells you both directories were checked
4. ✅ **Comprehensive Fix** - Preview, list, and delete all work correctly
5. ✅ **Debug Friendly** - Detailed logging for troubleshooting

## File Locations

- **PDFs**: `W:\bOt\uploaded_pdfs\`
  - Example: `hjkl_emp1_113207df.pdf`

- **Other Documents**: `W:\bOt\uploaded_documents\`
  - Example: `hjkl_emp1_650b6c6e.docx`
  - Example: `hjkl_emp1_bc0f690a.md`

## Summary

The document preview system now intelligently checks both directories and returns the file from wherever it's found. This fixes the "Document file not found" error for PDFs while maintaining compatibility with all other document types.
