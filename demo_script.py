import json
import random
from datetime import datetime, timedelta

def create_fake_ticket(ticket_id):
    """Generates a dictionary representing a single fake ticket."""
    statuses = ["Open", "In Progress", "Resolved", "Closed", "Pending Input"]
    assignees = ["jdoe", "asmith", "rpatel", "lchen", "mgarcia"]
    
    # Generate a realistic creation date within the last 30 days
    created_date = datetime.now() - timedelta(days=random.randint(0, 30))
    
    return {
        "ID": ticket_id,
        "Title": f"Failure in component {random.randint(100, 999)}",
        "Status": random.choice(statuses),
        "AssignedTo": random.choice(assignees),
        "Created": created_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "Severity": random.choice(["Critical", "High", "Medium", "Low"])
    }

def generate_demo_data():
    """Generates a structured dictionary of fake SharePoint data."""
    print("Generating fake SharePoint data for the demo...")
    
    demo_data = {
        "FireTV Testing Trackers": {
            "Internal Tickets Demo": [create_fake_ticket(i) for i in range(1, 21)],
            "Archived Issues (Demo)": [create_fake_ticket(i) for i in range(101, 108)]
        },
        "FireTV Production Metrics (Demo)": {
            "System Alerts": [create_fake_ticket(i) for i in range(201, 215)]
        }
    }
    
    return demo_data

if __name__ == "__main__":
    # Generate the data
    sharepoint_data = generate_demo_data()

    # Save the data to a JSON file
    output_filename = 'data.json'
    with open(output_filename, 'w') as f:
        json.dump(sharepoint_data, f, indent=4)
    
    print(f"Demo data successfully generated and saved to {output_filename}")
