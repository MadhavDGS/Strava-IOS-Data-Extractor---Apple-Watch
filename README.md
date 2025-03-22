# Strava Integration

This module handles integration with the Strava API to fetch activity data.

## Setup

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Create .env file:
```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

3. Run the sync:
```bash
python strava_sync.py
```

## Features
- Fetches recent activities from Strava
- Shows detailed activity information
- Auto-refreshes every 5 minutes
- Handles OAuth authentication 