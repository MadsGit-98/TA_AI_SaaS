# API Contract: Home Page Endpoints

## Home Page Content API

### GET /api/homepage-content/
**Purpose:** Retrieve configurable content for the home page

**Request:**
- Method: GET
- URL: `/api/homepage-content/`
- Headers: None required (public endpoint)
- Parameters: None

**Response:**
```json
{
  "title": "string - Main headline for the home page",
  "subtitle": "string - Subtitle or tagline",
  "description": "string - Main description of the service",
  "call_to_action_text": "string - Text for the main CTA button",
  "pricing_info": "string - Information about pricing plans",
  "last_updated": "datetime - ISO 8601 timestamp of last content update"
}
```

**Status Codes:**
- 200: Success - Content retrieved successfully
- 500: Server Error - Issue retrieving content from database

## Legal Pages API

### GET /api/legal-pages/{slug}/
**Purpose:** Retrieve content for a specific legal page (privacy policy, terms, etc.)

**Request:**
- Method: GET
- URL: `/api/legal-pages/{slug}/`
- Headers: None required (public endpoint)
- Parameters: 
  - `slug` (path parameter): URL-friendly identifier for the legal page

**Response:**
```json
{
  "title": "string - Title of the legal page",
  "content": "string - Full HTML content of the legal page",
  "page_type": "enum - Type of legal page ('privacy', 'terms', 'refund', 'contact')",
  "last_updated": "datetime - ISO 8601 timestamp of last content update"
}
```

**Status Codes:**
- 200: Success - Legal page content retrieved
- 404: Not Found - Legal page with the given slug does not exist
- 500: Server Error - Issue retrieving content from database

## Card Logos API

### GET /api/card-logos/
**Purpose:** Retrieve information about accepted payment card logos for display

**Request:**
- Method: GET
- URL: `/api/card-logos/`
- Headers: None required (public endpoint)
- Parameters: None

**Response:**
```json
[
  {
    "id": "integer - Primary key",
    "name": "string - Name of the card type",
    "logo_url": "string - URL to the card logo image",
    "display_order": "integer - Order in which to display the logos"
  }
]
```

**Status Codes:**
- 200: Success - Card logos retrieved successfully
- 500: Server Error - Issue retrieving content from database