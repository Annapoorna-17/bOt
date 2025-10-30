# Widget Implementation Guide

## Overview

This document explains the new embeddable chatbot widget feature that allows companies to add a RAG-powered chatbot to their websites, and the super-admin company query feature.

## Features Implemented

### 1. Embeddable Chatbot Widget
- **Public widget** that can be embedded on any company's website
- **Secure authentication** using widget keys
- **Queries company data** (documents and websites) without exposing sensitive credentials
- **Beautiful UI** with responsive design
- **Easy integration** with just a few lines of code

### 2. Widget Management (Admin Interface)
- **Generate widget keys** for each company
- **Regenerate keys** if compromised
- **Copy embed code** with one click
- **Integration instructions** for easy deployment

### 3. Super-Admin Company Chat
- **Query any company's data** directly from the admin panel
- **Test chatbots** before companies deploy them
- **Support and debugging** capabilities

## Backend Changes

### New Database Fields

#### Company Model (`app/models.py:12`)
```python
widget_key = Column(String(128), unique=True, nullable=True)
```

### New API Endpoints

#### 1. Get/Generate Widget Key
```
GET /widget/{tenant_code}/key
Authorization: Bearer {superadmin_token}
```

Response:
```json
{
  "tenant_code": "company1",
  "widget_key": "wk_abc123...",
  "company_name": "Company Name"
}
```

#### 2. Regenerate Widget Key
```
POST /widget/{tenant_code}/regenerate
Authorization: Bearer {superadmin_token}
```

Response:
```json
{
  "tenant_code": "company1",
  "widget_key": "wk_new456...",
  "company_name": "Company Name",
  "message": "Widget key regenerated successfully"
}
```

#### 3. Public Widget Query
```
POST /widget/query?widget_key={widget_key}
Content-Type: application/json

{
  "question": "What is your return policy?",
  "top_k": 5,
  "user_filter": false
}
```

Response:
```json
{
  "answer": "Our return policy allows...",
  "sources": ["policy.pdf", "https://example.com/faq"]
}
```

#### 4. Super-Admin Company Query
```
POST /widget/superadmin/query/{tenant_code}
Authorization: Bearer {superadmin_token}
Content-Type: application/json

{
  "question": "What products do you offer?",
  "top_k": 5,
  "user_filter": false
}
```

Response:
```json
{
  "answer": "We offer the following products...",
  "sources": ["catalog.pdf", "products.xlsx"]
}
```

## Frontend Changes

### New Components

#### 1. WidgetConfigDialog (`W:\ChatbotReact\src\components\dialogs\WidgetConfigDialog.tsx`)
- Shows widget key
- Provides embed code
- Includes integration instructions
- Allows key regeneration

#### 2. CompanyChatDialog (`W:\ChatbotReact\src\components\dialogs\CompanyChatDialog.tsx`)
- Chat interface for super-admin
- Query any company's data
- View sources for answers

### Updated Components

#### CompanyList (`W:\ChatbotReact\src\pages\admin\CompanyList.tsx`)
- Added "Widget Config" button (🧩 icon)
- Added "Chat with Company" button (💬 icon)
- Both buttons visible in the Actions column

### New Services

#### company.service.ts
```typescript
// Get widget key for a company
export async function getWidgetKey(tenantCode: string)

// Regenerate widget key
export async function regenerateWidgetKey(tenantCode: string)

// Query company data (super-admin only)
export async function queryCompanyData(tenantCode: string, question: string, topK: number = 5)
```

## Embeddable Widget

### File Location
`W:\bOt\widget\chatbot-widget.html`

### Features
- **Standalone HTML file** with embedded CSS and JavaScript
- **No dependencies** - works on any website
- **Responsive design** - works on mobile and desktop
- **Minimizable** - starts as a floating button
- **Beautiful gradient UI** with smooth animations
- **Typing indicators** while loading
- **Source citations** for transparency

### Configuration
Edit the `WIDGET_CONFIG` object in the HTML file:

```javascript
const WIDGET_CONFIG = {
    apiUrl: 'http://127.0.0.1:8000',  // Your API URL
    widgetKey: 'wk_abc123...',         // Widget key from admin panel
};
```

### Integration Methods

#### Method 1: Embed Script (Recommended)
```html
<!-- Add before closing </body> tag -->
<script>
  window.WIDGET_CONFIG = {
    apiUrl: 'https://your-api.com',
    widgetKey: 'wk_abc123...'
  };
</script>
<script src="https://your-api.com/static/chatbot-widget.js"></script>
```

#### Method 2: Standalone File
1. Download `chatbot-widget.html`
2. Update `WIDGET_CONFIG` with your values
3. Host the file on your website
4. Link to it or embed it in an iframe

## Usage Flow

### For Super-Admin

1. **Create a company** via the admin panel
2. **View companies** in the Companies list
3. **Click the Widget icon (🧩)** to get the widget configuration
4. **Copy the widget key** or embed code
5. **Click the Chat icon (💬)** to test the chatbot with company data

### For Company Admin

1. **Upload documents** and **scrape websites** via the admin panel
2. **Request widget key** from super-admin
3. **Add embed code** to your website
4. **Test the chatbot** on your site

### For End Users (Website Visitors)

1. **Visit the company website** with the widget installed
2. **Click the chat bubble** in the bottom-right corner
3. **Ask questions** about the company's products/services
4. **Get AI-powered answers** from the company's knowledge base

## Security Considerations

### Widget Key Security
- Widget keys are **public** (visible in client-side code)
- Keys only allow **read access** to company data via the query endpoint
- Keys **do not** allow document uploads, deletions, or other write operations
- Regenerate keys if compromised

### Rate Limiting (TODO)
Consider adding rate limiting to the public widget endpoint to prevent abuse:
- Per widget key: 100 requests/minute
- Per IP: 20 requests/minute
- Per session: 50 requests/hour

### CORS Configuration
The backend already has CORS enabled for all origins. For production:
```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trusted-domain.com"],  # Limit to specific domains
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)
```

## Testing

### 1. Start the Backend
```bash
cd W:\bOt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the Frontend
```bash
cd W:\ChatbotReact
npm run dev
```

### 3. Test Super-Admin Features
1. Login as super-admin
2. Go to Companies page
3. Click Widget icon on a company
4. Copy widget key
5. Click Chat icon to test querying

### 4. Test Embeddable Widget
1. Open `W:\bOt\widget\chatbot-widget.html` in a browser
2. Update `WIDGET_CONFIG.widgetKey` with a valid key
3. Click the chat bubble
4. Ask a question
5. Verify the response and sources

## Database Migration

The database migration automatically adds the `widget_key` column when the app starts:

```python
# app/db_migration.py:100
if add_column_if_missing("companies", "widget_key", "VARCHAR(128) NULL UNIQUE"):
    migrations_applied += 1
```

No manual migration is needed.

## Deployment Considerations

### Production Checklist

- [ ] Update API URL in frontend (`src/services/api.ts:4`)
- [ ] Update API URL in widget dialog (`WidgetConfigDialog.tsx:41`)
- [ ] Configure CORS for production domains
- [ ] Add rate limiting to widget endpoint
- [ ] Use HTTPS for API endpoints
- [ ] Host widget file on CDN for better performance
- [ ] Monitor widget usage and costs
- [ ] Set up error tracking (Sentry, etc.)

### Environment Variables

No new environment variables are required. The feature uses existing:
- `SUPERADMIN_TOKEN` - for widget key management
- `OPENAI_API_KEY` - for answering questions
- `PINECONE_API_KEY` - for vector search

## Future Enhancements

### Planned Features
- [ ] Widget customization (colors, position, branding)
- [ ] Analytics dashboard (widget usage, popular questions)
- [ ] Rate limiting and quota management
- [ ] Multi-language support
- [ ] Chat history for users
- [ ] File attachment support in widget
- [ ] Voice input/output
- [ ] Integration with popular CMS platforms (WordPress, Shopify, etc.)

### Advanced Features
- [ ] A/B testing for widget placement
- [ ] Lead capture integration
- [ ] CRM integration (Salesforce, HubSpot)
- [ ] Custom training workflows
- [ ] Widget performance metrics

## Troubleshooting

### Widget Key Not Working
- Verify the widget key in the database: `SELECT widget_key FROM companies WHERE tenant_code = 'xxx';`
- Check browser console for errors
- Verify API URL is correct and accessible

### CORS Errors
- Check CORS configuration in `app/main.py`
- Ensure the frontend domain is allowed
- For local development, use `allow_origins=["*"]`

### Chat Not Responding
- Check browser network tab for failed requests
- Verify the company has uploaded documents or scraped websites
- Check Pinecone index for data
- Review backend logs for errors

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the API documentation in `CLAUDE.md`
3. Check backend logs for error messages
4. Contact the development team

---

**Last Updated:** 2025-10-30
**Version:** 1.0.0
