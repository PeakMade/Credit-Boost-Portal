"""
Fetch resident data from CredHub for a specific job ID
Retrieves the first 100 consumers and saves to JSON
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class CredHubClient:
    """Client for CredHub API interactions"""
    
    def __init__(self, base_url: str, client_id: str, client_secret: str, audience: str, auth_endpoint: str):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = audience
        self.auth_endpoint = auth_endpoint
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})
    
    def get_token(self) -> str:
        """Get or refresh access token."""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < (self._token_expires_at - timedelta(seconds=60)):
                print("✓ Using cached access token")
                return self._access_token
        
        print("Requesting new access token from CredHub...")
        
        # Build full auth URL (handle relative or absolute endpoint)
        if self.auth_endpoint.startswith('http'):
            auth_url = self.auth_endpoint
        else:
            auth_url = f"{self.base_url}{self.auth_endpoint}"
        
        print(f"  Auth URL: {auth_url}")
        
        # Request new token
        response = requests.post(
            auth_url,
            json={
                "clientid": self.client_id,
                "clientsecret": self.client_secret,
                "audience": self.audience,
                "grant_type": "client_credentials"
            },
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        self._access_token = data["accessToken"]
        expires_in = data.get("expiresIn", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        print(f"✓ Access token acquired (expires in {expires_in} seconds)")
        return self._access_token
    
    def _get_headers(self) -> dict:
        """Get headers with access token."""
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_job_consumers(self, job_id: str, skip: int = 0, top: int = 100) -> dict:
        """Get job consumers with pagination."""
        print(f"\nFetching consumers from CredHub...")
        print(f"  Job ID: {job_id}")
        print(f"  Skip: {skip}")
        print(f"  Top: {top}")
        
        url = f"{self.base_url}/jobs/{job_id}/consumers"
        params = {"$skip": skip, "$top": top, "$expand": "jointConsumers"}
        
        response = self._session.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        print(f"✓ Response received (status {response.status_code})")
        return response.json()
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()


def main():
    """Main function to fetch CredHub job data"""
    
    # Job ID to fetch
    JOB_ID = "0d69f1fd-a7f2-4a57-9106-5d3c00a9090a"
    
    # Load configuration from environment
    print("=" * 80)
    print("CredHub Job Data Fetcher")
    print("=" * 80)
    
    base_url = os.getenv('CREDHUB_BASE_URL')
    client_id = os.getenv('CREDHUB_CLIENT_ID')
    client_secret = os.getenv('CREDHUB_CLIENT_SECRET')
    audience = os.getenv('CREDHUB_AUDIENCE')
    auth_endpoint = os.getenv('CREDHUB_AUTH_ENDPOINT')
    
    # Validate configuration
    missing = []
    if not base_url:
        missing.append('CREDHUB_BASE_URL')
    if not client_id:
        missing.append('CREDHUB_CLIENT_ID')
    if not client_secret:
        missing.append('CREDHUB_CLIENT_SECRET')
    if not audience:
        missing.append('CREDHUB_AUDIENCE')
    if not auth_endpoint:
        missing.append('CREDHUB_AUTH_ENDPOINT')
    
    if missing:
        print(f"\n❌ Error: Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease add these to your .env file")
        return
    
    print(f"\nConfiguration:")
    print(f"  Base URL: {base_url}")
    print(f"  Client ID: {client_id[:10]}...")
    print(f"  Audience: {audience}")
    print(f"  Auth Endpoint: {auth_endpoint}")
    
    try:
        # Create CredHub client
        client = CredHubClient(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            audience=audience,
            auth_endpoint=auth_endpoint
        )
        
        # Fetch first 100 consumers
        print(f"\n{'=' * 80}")
        print(f"Fetching first 100 consumers for job: {JOB_ID}")
        print(f"{'=' * 80}")
        
        response = client.get_job_consumers(job_id=JOB_ID, skip=0, top=100)
        
        # Extract consumers
        consumers = response.get("value", [])
        
        print(f"\n✓ Retrieved {len(consumers)} consumers")
        
        # Display summary
        if consumers:
            print(f"\nSample consumer:")
            sample = consumers[0]
            print(f"  Consumer ID: {sample.get('ConsumerId', 'N/A')}")
            print(f"  Account Number: {sample.get('AccountNumber', 'N/A')}")
            print(f"  Name: {sample.get('FirstName', '')} {sample.get('LastName', '')}")
            print(f"  Validation Status: {sample.get('ValidationStatus', 'N/A')}")
            
            # Count validation statuses
            status_counts = {}
            error_count = 0
            warning_count = 0
            
            for consumer in consumers:
                status = consumer.get('ValidationStatus', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if consumer.get('ComplianceErrors'):
                    error_count += 1
                if consumer.get('ComplianceWarnings'):
                    warning_count += 1
            
            print(f"\nValidation Summary:")
            for status, count in status_counts.items():
                print(f"  {status}: {count}")
            print(f"  Consumers with errors: {error_count}")
            print(f"  Consumers with warnings: {warning_count}")
        
        # Save to JSON file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"credhub_job_{JOB_ID[:8]}_consumers_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Data saved to: {filename}")
        print(f"  Total size: {len(json.dumps(response))} bytes")
        
        # Check for next link
        if "@odata.nextLink" in response:
            print(f"\n⚠️ More data available - use nextLink to fetch additional pages")
            print(f"   Next link: {response['@odata.nextLink']}")
        else:
            print(f"\n✓ All available data retrieved (no additional pages)")
        
        # Close client
        client.close()
        
        print(f"\n{'=' * 80}")
        print("✓ Complete!")
        print(f"{'=' * 80}")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request Error: {str(e)}")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
