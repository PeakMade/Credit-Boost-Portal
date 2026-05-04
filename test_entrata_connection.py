"""
Test script to verify Entrata API connection and retrieve resident data.
Saves results to JSON for inspection.
"""
import json
import logging
import sys
from datetime import datetime
from utils.entrata_api import get_entrata_client
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def test_entrata_connection():
    """Test Entrata API connection and retrieve lease data"""
    
    logger.info("=" * 80)
    logger.info("ENTRATA API CONNECTION TEST")
    logger.info("=" * 80)
    
    # Initialize client
    client = get_entrata_client()
    
    # Test 1: Get leases with demographics and transactions
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Retrieving leases with demographics and AR transactions")
    logger.info("=" * 80)
    
    try:
        # Get leases for specific property with recent move-ins
        leases = client.get_leases(
            property_id="100162547",  # Specific property ID
            move_in_from="03/01/2026",  # Previous month (March 2026)
            move_in_to="03/31/2026",
            include_demographics=True,
            include_ar_transactions=True
        )
        
        if leases is None:
            logger.error("❌ Failed to retrieve leases - check API credentials and permissions")
            return False
        
        logger.info(f"✅ Successfully retrieved {len(leases)} leases")
        
        # Save raw response to JSON
        output_file = f"entrata_leases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(leases, f, indent=2)
        logger.info(f"📁 Raw data saved to: {output_file}")
        
        # Display summary of first few leases
        logger.info("\n" + "=" * 80)
        logger.info("LEASE SUMMARY (first 5 leases)")
        logger.info("=" * 80)
        
        for i, lease in enumerate(leases[:5], 1):
            logger.info(f"\nLease #{i}:")
            logger.info(f"  Lease ID: {lease.get('id')}")
            logger.info(f"  Property: {lease.get('propertyName')}")
            
            # Unit info
            unit_spaces = lease.get('unitSpaces', {}).get('unitSpace', [])
            if isinstance(unit_spaces, dict):
                unit_spaces = [unit_spaces]
            units = [u.get('unitSpace') for u in unit_spaces]
            logger.info(f"  Units: {', '.join(units) if units else 'N/A'}")
            
            # Dates
            logger.info(f"  Lease Start: {lease.get('leaseStartDate')}")
            logger.info(f"  Move-In: {lease.get('moveInDate')}")
            logger.info(f"  Move-Out: {lease.get('moveOutDate', 'N/A')}")
            
            # Customers (residents)
            customers = lease.get('customers', {}).get('customer', [])
            if isinstance(customers, dict):
                customers = [customers]
            
            logger.info(f"  Residents ({len(customers)}):")
            for customer in customers:
                logger.info(f"    - {customer.get('firstName')} {customer.get('lastName')} ({customer.get('customerType')})")
                logger.info(f"      Email: {customer.get('emailAddress', 'N/A')}")
                logger.info(f"      DOB: {customer.get('dateOfBirth', 'N/A')}")
            
            # Scheduled charges
            charges = lease.get('scheduledCharges', {}).get('scheduledCharge', [])
            if isinstance(charges, dict):
                charges = [charges]
            
            if charges:
                rent_charge = next((c for c in charges if 'RENT' in c.get('chargeCode', '')), charges[0])
                logger.info(f"  Monthly Rent: ${rent_charge.get('amount', 'N/A')}")
            
            # AR Transactions count
            ar_trans = lease.get('arTransactions', {}).get('arTransaction', [])
            if isinstance(ar_trans, dict):
                ar_trans = [ar_trans]
            logger.info(f"  AR Transactions: {len(ar_trans)}")
        
        # Summary statistics
        logger.info("\n" + "=" * 80)
        logger.info("OVERALL STATISTICS")
        logger.info("=" * 80)
        
        total_residents = 0
        total_transactions = 0
        for lease in leases:
            customers = lease.get('customers', {}).get('customer', [])
            if isinstance(customers, dict):
                customers = [customers]
            total_residents += len(customers)
            
            ar_trans = lease.get('arTransactions', {}).get('arTransaction', [])
            if isinstance(ar_trans, dict):
                ar_trans = [ar_trans]
            total_transactions += len(ar_trans)
        
        logger.info(f"  Total Leases: {len(leases)}")
        logger.info(f"  Total Residents: {total_residents}")
        logger.info(f"  Total AR Transactions: {total_transactions}")
        logger.info(f"  Average Residents per Lease: {total_residents / len(leases):.2f}")
        logger.info(f"  Average Transactions per Lease: {total_transactions / len(leases):.2f}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ TEST COMPLETE - API connection successful!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during test: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_entrata_connection()
    sys.exit(0 if success else 1)
