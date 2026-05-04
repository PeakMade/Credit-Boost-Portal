# Entrata API Integration Guide

Complete guide for integrating with Entrata's API to retrieve lease, resident, and transaction data.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Required Credentials](#required-credentials)
4. [Environment Variables](#environment-variables)
5. [API Endpoints](#api-endpoints)
6. [Authentication Process](#authentication-process)
7. [Making API Calls](#making-api-calls)
8. [Response Structure](#response-structure)
9. [Code Examples](#code-examples)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Entrata provides a REST API for accessing property management data including:
- Lease information
- Resident demographics
- AR transactions (payments and charges)
- Scheduled charges
- Unit and property details

**Integration Method:** API Key Authentication  
**Protocol:** HTTPS POST requests with JSON payloads  
**Base URL:** `https://apis.entrata.com/ext/orgs/{organization}/v1/{group}`

---

## Prerequisites

Before starting, you need:

1. **Entrata Account** with API access enabled
2. **API Key** provisioned by Entrata support
3. **Organization Subdomain** (e.g., `peakmade`, `peakmade-test-17291`)
4. **API Permissions** for required data:
   - Lease data access
   - Demographics data access (optional, for `includeDemographics`)
   - AR Transactions data access (optional, for `includeArTransactions`)

> **Note:** Contact Entrata support to provision API keys and grant necessary permissions.

---

## Required Credentials

### 1. API Key
- **Format:** UUID (e.g., `8e383808-eeae-4aa7-b838-08eeae7aa7e2`)
- **Usage:** Sent in HTTP header `X-Api-Key`
- **Scope:** Tied to specific organization(s) and permissions
- **Security:** Treat as sensitive credential - never commit to version control

### 2. Organization Subdomain
- **Production Example:** `peakmade`
- **Sandbox Example:** `peakmade-test-17291`
- **Usage:** Part of API base URL
- **Note:** API keys are typically scoped to one environment (prod OR sandbox)

### 3. API Username (Optional)
- **Format:** `{uuid}.{organization}` (e.g., `67e16499ccd0432947fc.peakmade`)
- **Usage:** May be required for certain authentication flows (not used in our integration)

---

## Environment Variables

Store credentials securely in a `.env` file (never commit this file):

```bash
# Entrata API Configuration
ENTRATA_API_KEY=8e383808-eeae-4aa7-b838-08eeae7aa7e2
ENTRATA_API_USERNAME=67e16499ccd0432947fc.peakmade
ENTRATA_ORG_SUBDOMAIN=peakmade

# Optional: Separate sandbox credentials
ENTRATA_SANDBOX_API_KEY=your-sandbox-api-key-here
ENTRATA_SANDBOX_ORG_SUBDOMAIN=peakmade-test-17291
```

### `.gitignore` Entry
Always add to `.gitignore`:
```
.env
*.env
.env.local
```

---

## API Endpoints

### Primary Endpoint Used: `getLeases`

**Purpose:** Retrieve lease data with optional demographics and transaction history

**Endpoint Details:**
- **Method Name:** `getLeases`
- **Version:** `r2` (latest)
- **Group:** `leases`
- **Full URL:** `https://apis.entrata.com/ext/orgs/{organization}/v1/leases`

### Available Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `propertyId` | integer | No | Filter by specific property | `1122966` |
| `moveInDateFrom` | string | No | Filter leases by move-in date (MM/DD/YYYY) | `"01/01/2025"` |
| `moveInDateTo` | string | No | Filter leases by move-in date (MM/DD/YYYY) | `"12/31/2026"` |
| `includeDemographics` | string | No | Include resident profile data (`"0"` or `"1"`) | `"1"` |
| `includeArTransactions` | string | No | Include AR transaction history (`"0"` or `"1"`) | `"1"` |

### Other Available Endpoints

While we only use `getLeases`, Entrata provides other endpoints:
- `getResidents` - Resident-only data
- `getArTransactions` - Standalone AR transaction data
- `getMitsCollections` - Collections data
- `getProperties` - Property information
- `getUnits` - Unit details

---

## Authentication Process

Entrata uses **API Key Authentication** with a dual approach:

### 1. HTTP Header Authentication
Send API key in request header:
```http
X-Api-Key: 8e383808-eeae-4aa7-b838-08eeae7aa7e2
Content-Type: application/json
```

### 2. Request Body Authentication Declaration
Include auth object in JSON body:
```json
{
  "auth": {
    "type": "apikey"
  }
}
```

### Complete Authentication Flow

1. Load API key from environment variable
2. Construct base URL with organization subdomain
3. Set `X-Api-Key` header with API key value
4. Include `"auth": {"type": "apikey"}` in request body
5. POST request to endpoint
6. Receive response (200 = success, 400/403 = auth error)

**No OAuth, no tokens, no session management** - authentication is stateless.

---

## Making API Calls

### HTTP Request Structure

**Method:** `POST`

**URL:**
```
https://apis.entrata.com/ext/orgs/{organization}/v1/{group}
```

**Headers:**
```http
X-Api-Key: {your-api-key}
Content-Type: application/json
```

**Body:**
```json
{
  "auth": {
    "type": "apikey"
  },
  "requestId": "1709697845",
  "method": {
    "name": "getLeases",
    "version": "r2",
    "params": {
      "propertyId": 1122966,
      "moveInDateFrom": "01/01/2025",
      "moveInDateTo": "12/31/2026",
      "includeDemographics": "1",
      "includeArTransactions": "1"
    }
  }
}
```

### Request Components

#### `auth` (Required)
```json
"auth": {
  "type": "apikey"
}
```
Declares authentication method.

#### `requestId` (Required)
```json
"requestId": "1709697845"
```
Unique identifier for request tracking. Use timestamp or UUID.

#### `method` (Required)
```json
"method": {
  "name": "getLeases",
  "version": "r2",
  "params": { ... }
}
```
- **name:** API endpoint name
- **version:** API version (use `r2` for latest getLeases)
- **params:** Endpoint-specific parameters

---

## Response Structure

### Success Response (200)

```json
{
  "response": {
    "requestId": "1709697845",
    "code": 200,
    "result": {
      "leases": {
        "lease": [
          {
            "id": "15192877",
            "propertyName": "48 West",
            "unitSpaces": {
              "unitSpace": [
                {
                  "unitSpace": "101"
                }
              ]
            },
            "leaseStartDate": "01/15/2025",
            "moveInDate": "01/15/2025",
            "customers": {
              "customer": [
                {
                  "id": "18524700",
                  "customerType": "Primary",
                  "firstName": "John",
                  "lastName": "Doe",
                  "dateOfBirth": "01/15/1990",
                  "emailAddress": "john.doe@example.com",
                  "addresses": {
                    "address": [
                      {
                        "addressType": "primary",
                        "streetLine": "123 Main St",
                        "city": "Denver",
                        "state": "CO",
                        "postalCode": "80202"
                      }
                    ]
                  }
                }
              ]
            },
            "scheduledCharges": {
              "scheduledCharge": [
                {
                  "frequency": "Monthly",
                  "amount": "1500.00",
                  "chargeCode": "RENT",
                  "description": "Base Rent"
                }
              ]
            },
            "arTransactions": {
              "arTransaction": [
                {
                  "postDate": "02/01/2026",
                  "transactionTypeId": "2",
                  "amount": "1500.00",
                  "description": "Rent Charge"
                },
                {
                  "postDate": "02/05/2026",
                  "transactionTypeId": "1",
                  "amount": "-1500.00",
                  "description": "Payment"
                }
              ]
            }
          }
        ]
      }
    }
  }
}
```

### Error Response (400/403)

```json
{
  "response": {
    "requestId": "1709697845",
    "code": 400,
    "error": {
      "code": 1403,
      "message": "The 'orgs' is not associated with the application"
    }
  }
}
```

### Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process result data |
| 400 | Bad Request | Check request format and parameters |
| 403 | Forbidden | Verify API key and permissions |
| 404 | Not Found | Check organization subdomain and endpoint |
| 500 | Server Error | Retry or contact Entrata support |

---

## Code Examples

### Python Implementation

```python
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
ENTRATA_API_BASE = "https://apis.entrata.com/ext/orgs"
ENTRATA_ORG = os.getenv("ENTRATA_ORG_SUBDOMAIN", "peakmade")
ENTRATA_API_KEY = os.getenv("ENTRATA_API_KEY")

def call_entrata_api(endpoint, group="leases", params=None, version=None):
    """
    Make a request to Entrata API.
    
    Args:
        endpoint: API method name (e.g., "getLeases")
        group: API group (e.g., "leases")
        params: Dictionary of endpoint parameters
        version: API version (e.g., "r2")
    
    Returns:
        Dictionary with API response result
    """
    url = f"{ENTRATA_API_BASE}/{ENTRATA_ORG}/v1/{group}"
    
    headers = {
        "X-Api-Key": ENTRATA_API_KEY,
        "Content-Type": "application/json",
    }
    
    method_obj = {
        "name": endpoint,
        "params": params or {},
    }
    
    if version:
        method_obj["version"] = version
    
    request_body = {
        "auth": {"type": "apikey"},
        "requestId": str(int(datetime.now().timestamp())),
        "method": method_obj,
    }
    
    response = requests.post(url, headers=headers, json=request_body)
    
    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")
    
    result = response.json()
    
    # Check for API-level errors
    if result.get("response", {}).get("code") != 200:
        error = result.get("response", {}).get("error", {})
        raise Exception(f"API error: {error.get('message', 'Unknown error')}")
    
    return result.get("response", {}).get("result", {})


# Example: Get leases with demographics and transactions
def get_leases(property_id=None):
    """Fetch leases from Entrata API."""
    params = {
        "moveInDateFrom": "01/01/2025",
        "moveInDateTo": "12/31/2026",
        "includeDemographics": "1",
        "includeArTransactions": "1",
    }
    
    if property_id:
        params["propertyId"] = int(property_id)
    
    result = call_entrata_api("getLeases", group="leases", params=params, version="r2")
    leases = result.get("leases", {}).get("lease", [])
    
    return leases


# Usage
if __name__ == "__main__":
    try:
        leases = get_leases(property_id=1122966)
        print(f"Retrieved {len(leases)} leases")
        
        for lease in leases[:5]:  # First 5 leases
            print(f"Lease ID: {lease.get('id')} | Property: {lease.get('propertyName')}")
    
    except Exception as e:
        print(f"Error: {e}")
```

### cURL Example

```bash
curl -X POST \
  https://apis.entrata.com/ext/orgs/peakmade/v1/leases \
  -H 'X-Api-Key: 8e383808-eeae-4aa7-b838-08eeae7aa7e2' \
  -H 'Content-Type: application/json' \
  -d '{
    "auth": {
      "type": "apikey"
    },
    "requestId": "1709697845",
    "method": {
      "name": "getLeases",
      "version": "r2",
      "params": {
        "propertyId": 1122966,
        "includeDemographics": "1",
        "includeArTransactions": "1"
      }
    }
  }'
```

---

## Troubleshooting

### Common Issues

#### 1. "The 'orgs' is not associated with the application"

**Error Code:** 1403  
**Cause:** API key is not authorized for the specified organization  
**Solution:**
- Verify organization subdomain matches API key
- Check if using production key with sandbox (or vice versa)
- Contact Entrata to add organization access to your API key

#### 2. "Invalid API Key" or 403 Forbidden

**Cause:** API key is incorrect or expired  
**Solution:**
- Verify API key in `.env` file matches Entrata-provided key
- Check for extra spaces or characters
- Confirm API key is active (contact Entrata if expired)

#### 3. Empty Response or Missing Data

**Cause:** Missing permissions for requested data  
**Solution:**
- Demographics missing: API key needs demographics permission
- AR transactions missing: API key needs AR transactions permission
- Contact Entrata to grant additional permissions

#### 4. 400 Bad Request - Invalid Parameters

**Cause:** Malformed request parameters  
**Solution:**
- Date format must be `MM/DD/YYYY` (not ISO format)
- Boolean flags must be strings: `"0"` or `"1"` (not `true`/`false`)
- PropertyId must be integer
- Check JSON syntax

#### 5. Rate Limiting

**Symptoms:** Intermittent 429 or 503 errors  
**Solution:**
- Implement exponential backoff
- Add delays between bulk requests
- Contact Entrata for rate limit increase if needed

---

## Best Practices

### Security
- ✅ Store API keys in environment variables
- ✅ Add `.env` to `.gitignore`
- ✅ Use separate keys for production/sandbox
- ✅ Rotate API keys periodically
- ❌ Never hardcode API keys in source code
- ❌ Never commit credentials to version control

### Performance
- Use `includeArTransactions` and `includeDemographics` flags only when needed
- Filter by `propertyId` when possible to reduce response size
- Implement pagination for large datasets
- Cache responses when appropriate

### Error Handling
- Always check response `code` field (should be 200)
- Handle network timeouts gracefully
- Log failed requests for debugging
- Implement retry logic with exponential backoff

### Data Validation
- Verify array vs single object responses (use `isinstance(data, list)`)
- Check for null/missing fields before accessing
- Validate date formats before parsing
- Handle missing nested objects gracefully

---

## Additional Resources

### Entrata Documentation
- API Documentation: Contact Entrata support for official API docs
- Developer Portal: May be available depending on your contract

### Support Contacts
- **API Issues:** Contact Entrata technical support
- **API Key Provisioning:** Submit request through Entrata support portal
- **Permission Changes:** Coordinate with Entrata account manager

---

## Appendix: Transaction Type IDs

Common AR transaction type IDs:

| Type ID | Description | Amount Convention |
|---------|-------------|-------------------|
| 1 | Payment | Negative (e.g., `-1500.00`) |
| 2 | Charge | Positive |
| 3 | Charge (Other) | Positive |
| 9 | Adjustment | Positive or Negative |

**Note:** Transaction types may vary by Entrata configuration. Verify with your Entrata representative.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | March 2026 | Initial documentation |

---

**Document Maintained By:** PeakMade Development Team  
**Last Updated:** March 13, 2026
