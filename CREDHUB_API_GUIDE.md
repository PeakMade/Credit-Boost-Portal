# CredHub API Integration Guide

Complete guide for authenticating and making API calls to the CredHub Credit Reporting as a Service (CRaaS) platform.

---

## Table of Contents

1. [Authentication](#authentication)
2. [API Endpoints](#api-endpoints)
3. [Common Patterns](#common-patterns)
4. [Error Handling](#error-handling)
5. [Code Examples](#code-examples)

---

## Authentication

### OAuth 2.0 Client Credentials Flow

CredHub uses OAuth 2.0 client credentials grant for machine-to-machine authentication.

#### Required Configuration

```bash
CREDHUB_BASE_URL=https://your-credhub-instance.com
CREDHUB_CLIENT_ID=your_client_id
CREDHUB_CLIENT_SECRET=your_client_secret
CREDHUB_AUDIENCE=CreditReportingSaaSQA01  # Or production audience
CREDHUB_AUTH_ENDPOINT=https://your-auth-server.com/connect/token
```

#### Authentication Request

**Endpoint:** `POST {CREDHUB_AUTH_ENDPOINT}`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "clientid": "your_client_id",
  "clientsecret": "your_client_secret",
  "audience": "CreditReportingSaaSQA01",
  "grant_type": "client_credentials"
}
```

**Response:**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 3600,
  "tokenType": "Bearer"
}
```

#### Token Management

- **Expiration:** Tokens typically expire after 1 hour (3600 seconds)
- **Caching:** Cache the token and reuse until 60 seconds before expiration
- **Refresh:** Request a new token when the cached token is within 60 seconds of expiring

#### Using the Token

Include the access token in all subsequent API requests:

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

---

## API Endpoints

All endpoints use the base URL configured in `CREDHUB_BASE_URL`.

### 1. Companies

#### Get Companies

Get a list of all companies registered in CredHub.

**Endpoint:** `GET /companies`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Response:**
```json
[
  {
    "companyId": "12345",
    "companyName": "ABC Property Management",
    "contactEmail": "contact@abcpm.com",
    "phoneNumber": "555-0100"
  }
]
```

**Notes:**
- Response format may vary (array, or object with `value` key for OData)
- Empty response if no companies exist

---

#### Create Company

Register a new company in CredHub.

**Endpoint:** `POST /companies`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body:**
```json
{
  "companyName": "ABC Property Management",
  "contactEmail": "contact@abcpm.com",
  "phoneNumber": "555-0100",
  "addressLine1": "123 Main St",
  "city": "Tampa",
  "state": "FL",
  "postalCode": "33602"
}
```

**Response:**
```json
{
  "companyId": "12345",
  "companyName": "ABC Property Management",
  "contactEmail": "contact@abcpm.com",
  "phoneNumber": "555-0100"
}
```

---

### 2. Credit Bureaus

#### Get Credit Bureaus

Get list of available credit bureaus for reporting.

**Endpoint:** `GET /creditBureaus`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Response:**
```json
[
  {
    "creditBureauId": "1",
    "creditBureauName": "Equifax"
  },
  {
    "creditBureauId": "2",
    "creditBureauName": "Experian"
  },
  {
    "creditBureauId": "3",
    "creditBureauName": "TransUnion"
  }
]
```

---

#### Get Company Credit Bureau Mappings

Get the credit bureaus a company is configured to report to.

**Endpoint:** `GET /companyCreditBureaus?companyId={companyId}`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Query Parameters:**
- `companyId` (string): The CredHub company ID

**Response:**
```json
[
  {
    "companyCreditBureauId": "1001",
    "companyId": "12345",
    "creditBureauId": "1",
    "creditBureauName": "Equifax",
    "isActive": true
  },
  {
    "companyCreditBureauId": "1002",
    "companyId": "12345",
    "creditBureauId": "2",
    "creditBureauName": "Experian",
    "isActive": true
  }
]
```

---

#### Create Company Credit Bureau Mapping

Configure a company to report to a specific credit bureau.

**Endpoint:** `POST /companyCreditBureaus`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body:**
```json
{
  "companyId": "12345",
  "creditBureauId": "1"
}
```

**Response:**
```json
{
  "companyCreditBureauId": "1001",
  "companyId": "12345",
  "creditBureauId": "1",
  "creditBureauName": "Equifax",
  "isActive": true
}
```

---

### 3. Rental Accounts Submission

#### Submit Rental Accounts

Submit rental payment data for credit reporting. This is the primary submission endpoint.

**Endpoint:** `POST /rentalAccounts`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body:**
```json
{
  "asOfDate": "2026-03-01",
  "companyId": "12345",
  "leases": [
    {
      "accountNumber": "A10001",
      "dateOfAccountInformation": "2026-03-01",
      "dateLastPayment": "2026-02-25",
      "totalPaymentAmountInPeriod": 1450.00,
      "totalMonthlyRecurringCharges": 1450.00,
      "monthlyRentAmount": 1400.00,
      "totalLedgerBalance": 0.00,
      "balanceAged30To59Days": 0.00,
      "balanceAged60To89Days": 0.00,
      "balanceAged90To119Days": 0.00,
      "balanceAged120To149Days": 0.00,
      "balanceAged150To179Days": 0.00,
      "balanceAged180DaysOrMore": 0.00,
      "oldestOpenChargeDate": null,
      "firstLineOfAddress": "123 Main St",
      "secondLineOfAddress": "Apt 4B",
      "city": "Tampa",
      "state": "FL",
      "postalZipCode": "33602",
      "country": "US",
      "moveInDate": "2025-07-01",
      "moveOutDate": null,
      "currentLeaseStartDate": "2025-07-01",
      "currentLeaseEndDate": "2026-06-30",
      "residents": [
        {
          "firstName": "Jane",
          "middleName": "A",
          "lastName": "Doe",
          "residentDateOfBirth": "1992-01-10",
          "residentPhoneNumber": "5551234567",
          "residentEmail": "jane@example.com",
          "reportToCreditBureaus": true,
          "leaseRelationship": "Primary",
          "isAddressSameAsPrimary": true
        }
      ]
    }
  ]
}
```

**Response:**
```json
{
  "jobId": "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a",
  "status": "Processing",
  "message": "Job submitted successfully"
}
```

**Important Notes:**
- `asOfDate`: Reporting cycle date (typically end of month)
- `accountNumber`: Must be unique per lease
- `residents[]`: At least one resident required per lease
- All date fields use ISO 8601 format (YYYY-MM-DD)
- Financial amounts are decimals
- Returns a `jobId` for tracking processing status

---

### 4. Job Status and Results

#### Get Job Consumers

Retrieve processed rental account data and validation results for a job.

**Endpoint:** `GET /jobs/{jobId}/consumers`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Path Parameters:**
- `jobId` (string): The job ID returned from rental accounts submission

**Query Parameters (OData):**
- `$skip` (integer): Number of records to skip (default: 0)
- `$top` (integer): Number of records to return (max: 100, default: 100)
- `$expand` (string): Expand related entities (use `jointConsumers` for joint account holders)

**Example URL:**
```
GET /jobs/0d69f1fd-a7f2-4a57-9106-5d3c00a9090a/consumers?$skip=0&$top=100&$expand=jointConsumers
```

**Response:**
```json
{
  "@odata.context": "https://api.credhub.com/$metadata#RentalAccountConsumers",
  "@odata.nextLink": "/jobs/{jobId}/consumers?$skip=100&$top=100",
  "value": [
    {
      "ConsumerId": "550e8400-e29b-41d4-a716-446655440000",
      "AccountNumber": "A10001",
      "FirstName": "Jane",
      "MiddleName": "A",
      "LastName": "Doe",
      "DateOfBirth": "1992-01-10",
      "PhoneNumber": "5551234567",
      "Email": "jane@example.com",
      "AddressLine1": "123 Main St",
      "AddressLine2": "Apt 4B",
      "City": "Tampa",
      "State": "FL",
      "PostalCode": "33602",
      "Country": "US",
      "DateOpened": "2025-07-01",
      "DateClosed": null,
      "CurrentLeaseStartDate": "2025-07-01",
      "CurrentLeaseEndDate": "2026-06-30",
      "MonthlyRentAmount": 1400.00,
      "TotalMonthlyRecurringCharges": 1450.00,
      "TotalLedgerBalance": 0.00,
      "DateOfAccountInformation": "2026-03-01",
      "DateLastPayment": "2026-02-25",
      "LastPaymentAmount": 1450.00,
      "ComplianceErrors": [],
      "ComplianceWarnings": [],
      "ValidationStatus": "Valid",
      "EcoaCode": "1",
      "PropertyId": "PROP001",
      "JointConsumers": []
    }
  ]
}
```

**Pagination:**
- Use `@odata.nextLink` to get next page if present
- Continue fetching until `@odata.nextLink` is null/absent

**Validation Status:**
- `Valid`: Passed all compliance checks
- `Warning`: Has warnings but can be reported
- `Error`: Has compliance errors, will not be reported

---

#### Get Job Status (Legacy)

Alternative endpoint for job status (may return different format).

**Endpoint:** `GET /jobs/{jobId}/status`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Response:**
```json
{
  "jobId": "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a",
  "status": "Completed",
  "submittedAt": "2026-03-01T10:30:00Z",
  "completedAt": "2026-03-01T10:35:00Z",
  "totalRecords": 150,
  "successCount": 145,
  "errorCount": 5
}
```

---

### 5. Job Re-Run

#### Re-Run Job

Re-process a job after fixing validation errors in source data.

**Endpoint:** `POST /jobs/ReRun`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body:**
```json
{
  "jobId": "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a",
  "companyId": "12345"
}
```

**Response:**
```json
{
  "jobId": "1a2b3c4d-5e6f-7890-abcd-ef1234567890",
  "status": "Processing",
  "message": "Job re-run submitted successfully"
}
```

**Notes:**
- Returns a new job ID for the re-run
- Original data is reprocessed with current validation rules

---

### 6. Metro2 File Generation

#### Generate Metro2 File

Generate Metro2 credit bureau file after job validation is complete.

**Endpoint:** `POST /Jobs/GenerateMetro2`

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body:**
```json
{
  "jobId": "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a",
  "companyId": "12345"
}
```

**Response:**
```json
{
  "jobId": "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a",
  "status": "Generating",
  "message": "Metro2 file generation initiated",
  "fileUrl": "https://files.credhub.com/metro2/..."
}
```

**Notes:**
- Job must be in `Completed` status with validation passed
- File URL provided when generation completes
- File contains credit bureau formatted data (Metro 2® Format)

---

## Common Patterns

### Full Reporting Workflow

1. **Setup (One-time)**
   ```
   POST /companies → Get companyId
   GET /creditBureaus → Get available bureaus
   POST /companyCreditBureaus → Enable reporting to bureaus
   ```

2. **Monthly Reporting Cycle**
   ```
   POST /rentalAccounts → Submit data, get jobId
   GET /jobs/{jobId}/consumers → Check status, get validation results
   (If errors: fix data → POST /jobs/ReRun)
   POST /Jobs/GenerateMetro2 → Generate bureau file
   ```

### Pagination Pattern

```python
def get_all_consumers(job_id, client):
    all_consumers = []
    skip = 0
    
    while True:
        response = client.get(
            f"/jobs/{job_id}/consumers",
            params={"$skip": skip, "$top": 100, "$expand": "jointConsumers"}
        )
        
        consumers = response["value"]
        all_consumers.extend(consumers)
        
        if "@odata.nextLink" not in response:
            break
            
        skip += 100
    
    return all_consumers
```

### Error Validation Pattern

```python
def analyze_validation_errors(consumers):
    errors = []
    warnings = []
    
    for consumer in consumers:
        if consumer.get("ComplianceErrors"):
            errors.append({
                "account": consumer["AccountNumber"],
                "errors": consumer["ComplianceErrors"]
            })
        if consumer.get("ComplianceWarnings"):
            warnings.append({
                "account": consumer["AccountNumber"],
                "warnings": consumer["ComplianceWarnings"]
            })
    
    return errors, warnings
```

---

## Error Handling

### HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Validation error (check response body for details)
- **401 Unauthorized**: Invalid or expired access token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found (invalid company ID, job ID, etc.)
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error (retry with exponential backoff)

### Authentication Errors

**Error Response:**
```json
{
  "error": "invalid_client",
  "error_description": "Client authentication failed"
}
```

**Solutions:**
- Verify `clientid` and `clientsecret` are correct
- Check that credentials are for the correct environment (sandbox vs production)
- Ensure audience matches your environment

### Validation Errors

**Error Response:**
```json
{
  "status": "ValidationFailed",
  "message": "Invalid payload",
  "errors": [
    {
      "field": "leases[0].accountNumber",
      "message": "Account number is required"
    },
    {
      "field": "leases[0].residents[0].residentDateOfBirth",
      "message": "Date of birth must be in the past"
    }
  ]
}
```

**Common Validation Issues:**
- Missing required fields
- Invalid date formats (use ISO 8601: YYYY-MM-DD)
- Invalid state codes (use 2-letter abbreviations)
- Negative financial amounts
- Future dates where not allowed

### Retry Strategy

Recommended retry logic for transient errors:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.RequestError)
)
def make_api_call():
    # API call here
    pass
```

---

## Code Examples

### Python Example (Using httpx)

```python
import httpx
from datetime import datetime, timedelta
from typing import Optional

class CredHubClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str, audience: str, auth_endpoint: str):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = audience
        self.auth_endpoint = auth_endpoint
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client = httpx.Client(base_url=base_url, timeout=30.0)
    
    def get_token(self) -> str:
        """Get or refresh access token."""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < (self._token_expires_at - timedelta(seconds=60)):
                return self._access_token
        
        # Request new token
        response = self._client.post(
            self.auth_endpoint,
            json={
                "clientid": self.client_id,
                "clientsecret": self.client_secret,
                "audience": self.audience,
                "grant_type": "client_credentials"
            }
        )
        response.raise_for_status()
        
        data = response.json()
        self._access_token = data["accessToken"]
        expires_in = data.get("expiresIn", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return self._access_token
    
    def _get_headers(self) -> dict:
        """Get headers with access token."""
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def submit_rental_accounts(self, payload: dict) -> dict:
        """Submit rental accounts for reporting."""
        response = self._client.post(
            "/rentalAccounts",
            headers=self._get_headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_job_consumers(self, job_id: str, skip: int = 0, top: int = 100) -> dict:
        """Get job consumers with pagination."""
        response = self._client.get(
            f"/jobs/{job_id}/consumers",
            headers=self._get_headers(),
            params={"$skip": skip, "$top": top, "$expand": "jointConsumers"}
        )
        response.raise_for_status()
        return response.json()
    
    def get_all_job_consumers(self, job_id: str) -> list:
        """Get all job consumers with automatic pagination."""
        all_consumers = []
        skip = 0
        
        while True:
            response = self.get_job_consumers(job_id, skip=skip, top=100)
            consumers = response.get("value", [])
            all_consumers.extend(consumers)
            
            if "@odata.nextLink" not in response:
                break
            
            skip += 100
        
        return all_consumers
    
    def close(self):
        """Close HTTP client."""
        self._client.close()

# Usage
client = CredHubClient(
    base_url="https://sandbox.credhub.example.com",
    client_id="your_client_id",
    client_secret="your_client_secret",
    audience="CreditReportingSaaSQA01",
    auth_endpoint="https://auth.credhub.example.com/connect/token"
)

# Submit rental accounts
payload = {
    "asOfDate": "2026-03-01",
    "companyId": "12345",
    "leases": [...]
}

result = client.submit_rental_accounts(payload)
job_id = result["jobId"]
print(f"Job ID: {job_id}")

# Get all consumers
consumers = client.get_all_job_consumers(job_id)
print(f"Total consumers: {len(consumers)}")

# Analyze validation
errors = [c for c in consumers if c.get("ComplianceErrors")]
print(f"Consumers with errors: {len(errors)}")

client.close()
```

### C# Example (Using HttpClient)

```csharp
using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

public class CredHubClient
{
    private readonly HttpClient _httpClient;
    private readonly string _clientId;
    private readonly string _clientSecret;
    private readonly string _audience;
    private readonly string _authEndpoint;
    private string _accessToken;
    private DateTime _tokenExpiresAt;

    public CredHubClient(string baseUrl, string clientId, string clientSecret, string audience, string authEndpoint)
    {
        _httpClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        _clientId = clientId;
        _clientSecret = clientSecret;
        _audience = audience;
        _authEndpoint = authEndpoint;
    }

    private async Task<string> GetTokenAsync()
    {
        if (!string.IsNullOrEmpty(_accessToken) && DateTime.UtcNow < _tokenExpiresAt.AddSeconds(-60))
        {
            return _accessToken;
        }

        var authRequest = new
        {
            clientid = _clientId,
            clientsecret = _clientSecret,
            audience = _audience,
            grant_type = "client_credentials"
        };

        var content = new StringContent(JsonSerializer.Serialize(authRequest), Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync(_authEndpoint, content);
        response.EnsureSuccessStatusCode();

        var authResponse = await JsonSerializer.DeserializeAsync<AuthResponse>(await response.Content.ReadAsStreamAsync());
        _accessToken = authResponse.AccessToken;
        _tokenExpiresAt = DateTime.UtcNow.AddSeconds(authResponse.ExpiresIn);

        return _accessToken;
    }

    private async Task<HttpRequestMessage> CreateRequestAsync(HttpMethod method, string endpoint)
    {
        var token = await GetTokenAsync();
        var request = new HttpRequestMessage(method, endpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return request;
    }

    public async Task<JobSubmissionResponse> SubmitRentalAccountsAsync(object payload)
    {
        var request = await CreateRequestAsync(HttpMethod.Post, "/rentalAccounts");
        request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");

        var response = await _httpClient.SendAsync(request);
        response.EnsureSuccessStatusCode();

        return await JsonSerializer.DeserializeAsync<JobSubmissionResponse>(await response.Content.ReadAsStreamAsync());
    }

    public async Task<JobConsumersResponse> GetJobConsumersAsync(string jobId, int skip = 0, int top = 100)
    {
        var request = await CreateRequestAsync(HttpMethod.Get, $"/jobs/{jobId}/consumers?$skip={skip}&$top={top}&$expand=jointConsumers");
        var response = await _httpClient.SendAsync(request);
        response.EnsureSuccessStatusCode();

        return await JsonSerializer.DeserializeAsync<JobConsumersResponse>(await response.Content.ReadAsStreamAsync());
    }
}

// Usage
var client = new CredHubClient(
    "https://sandbox.credhub.example.com",
    "your_client_id",
    "your_client_secret",
    "CreditReportingSaaSQA01",
    "https://auth.credhub.example.com/connect/token"
);

var payload = new { asOfDate = "2026-03-01", companyId = "12345", leases = new[] { ... } };
var result = await client.SubmitRentalAccountsAsync(payload);
Console.WriteLine($"Job ID: {result.JobId}");
```

---

## Latest Job ID Reference

**Most Recent Job ID:** `0d69f1fd-a7f2-4a57-9106-5d3c00a9090a`

**Date Used:** March 17, 2026

**Status:** Completed (used for data validation and analysis)

**Other Recent Job IDs:**
- `e8bd6a43-b0ca-4519-9518-2d188b6683c1` (March 13, 2026)
- `4c17406b-9797-4bd7-b21b-7f95ad426026` (March 13, 2026)

---

## Additional Resources

- **Implementation Code:** See `app/services/credhub_client.py` for full Python implementation
- **Data Mapping:** See `credhub_api_to_sharepoint_mapping.md` for field mappings
- **Workflow:** See `app/workflows/reporting_workflow.py` for complete reporting flow
- **Testing:** See `test_workflow.py` for testing different scenarios

---

## Support and Troubleshooting

### Common Issues

**Issue:** 401 Unauthorized  
**Solution:** Token expired or invalid. Request new token and retry.

**Issue:** 400 Validation Error  
**Solution:** Check response body for specific field errors. Verify date formats, required fields, and data types.

**Issue:** Empty consumers list  
**Solution:** Job may still be processing. Wait 30-60 seconds and retry. Check job status endpoint.

**Issue:** Pagination not working  
**Solution:** Ensure you're following the exact `@odata.nextLink` URL provided in the response.

### Best Practices

1. **Token Management:** Cache and reuse tokens until near expiration
2. **Error Handling:** Implement retry logic with exponential backoff for transient errors
3. **Pagination:** Always check for `@odata.nextLink` and fetch all pages
4. **Validation:** Validate data before submission to avoid unnecessary API calls
5. **Logging:** Log all request/response payloads for debugging
6. **Rate Limiting:** Respect rate limits and implement throttling if needed
7. **Testing:** Test with small payloads in sandbox before production submissions

---

*Last Updated: May 5, 2026*
