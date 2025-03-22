from stravalib import Client
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import time
import http.server
import socketserver
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs

# Load environment variables
load_dotenv()

# Global variable to store the authorization code
auth_code = None

class RedirectHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        # Parse the URL and get the code parameter
        query_components = parse_qs(urlparse(self.path).query)
        if 'code' in query_components:
            auth_code = query_components['code'][0]
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
            # Shutdown the server
            threading.Thread(target=self.server.shutdown, daemon=True).start()

class StravaDataFetcher:
    def __init__(self):
        self.client = Client()
        try:
            self.client_id = int(os.getenv('STRAVA_CLIENT_ID'))
        except (TypeError, ValueError):
            print("Error: STRAVA_CLIENT_ID must be a valid integer")
            self.client_id = None
        self.client_secret = os.getenv('STRAVA_CLIENT_SECRET')
        self.refresh_token = os.getenv('STRAVA_REFRESH_TOKEN')

    def start_local_server(self):
        # Create server
        with socketserver.TCPServer(("", 8000), RedirectHandler) as httpd:
            print("Server started at localhost:8000")
            httpd.serve_forever()

    def authenticate(self):
        """Handle Strava authentication"""
        try:
            if not self.client_id or not self.client_secret:
                print("\nError: Missing or invalid Strava credentials!")
                print("Please ensure you have set correct STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in your .env file")
                print(f"Current values:")
                print(f"STRAVA_CLIENT_ID={os.getenv('STRAVA_CLIENT_ID')}")
                print(f"STRAVA_CLIENT_SECRET={os.getenv('STRAVA_CLIENT_SECRET')}")
                return False

            if self.refresh_token:
                try:
                    # Try to refresh the token
                    token_response = self.client.refresh_access_token(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        refresh_token=self.refresh_token
                    )
                    self.client.access_token = token_response['access_token']
                    print("Token refreshed successfully!")
                    return True
                except Exception as e:
                    print(f"Error refreshing token: {str(e)}")
                    # Continue with new authentication if refresh fails
            
            # Start local server in a separate thread
            server_thread = threading.Thread(target=self.start_local_server, daemon=True)
            server_thread.start()

            # Generate authorization URL
            authorize_url = self.client.authorization_url(
                client_id=self.client_id,
                redirect_uri='http://localhost:8000',
                scope=['read_all', 'activity:read_all', 'profile:read_all']
            )

            # Open browser automatically
            print("\nOpening browser for authentication...")
            webbrowser.open(authorize_url)

            # Wait for the authorization code
            while auth_code is None:
                time.sleep(1)

            try:
                # Exchange the code for tokens
                token_response = self.client.exchange_code_for_token(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    code=auth_code
                )
                self.refresh_token = token_response['refresh_token']
                self.client.access_token = token_response['access_token']
                print("\nAuthentication successful!")
                print(f"\nIMPORTANT: Add this refresh token to your .env file:")
                print(f"STRAVA_REFRESH_TOKEN={self.refresh_token}")
                return True
            except Exception as e:
                print(f"\nError exchanging code for token: {str(e)}")
                return False
            
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return False

    def get_activities(self, days=1):
        """Fetch recent activities"""
        try:
            after = datetime.now() - timedelta(days=days)
            activities = self.client.get_activities(after=after)
            
            print("\nStrava Activities:")
            print("-----------------")
            
            activity_found = False
            for activity in activities:
                try:
                    activity_found = True
                    print(f"\nActivity: {activity.name}")
                    
                    # Format date to show both date and time
                    activity_date = activity.start_date_local
                    date_str = activity_date.strftime('%b %d, %Y at %I:%M %p').replace(' 0', ' ')  # Remove leading zero
                    print(f"Date: {date_str}")
                    
                    print(f"Type: {str(activity.type).replace('root=', '').replace("'", '')}")
                    
                    # Handle distance
                    if hasattr(activity, 'distance'):
                        distance_meters = float(activity.distance)
                        print(f"Distance: {distance_meters/1000:.2f} km")
                    
                    # Handle duration (moving time)
                    if hasattr(activity, 'moving_time'):
                        try:
                            # Convert the moving time to total seconds
                            if isinstance(activity.moving_time, (int, float)):
                                total_seconds = int(activity.moving_time)
                            else:
                                total_seconds = int(activity.moving_time.total_seconds())
                            
                            # Calculate hours and minutes
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            
                            # Format the time string
                            if hours > 0:
                                time_str = f"{hours}:{minutes:02d}:00"
                            else:
                                time_str = f"{minutes:02d}:00"
                            
                            print(f"Moving Time: {time_str}")
                            
                        except Exception as e:
                            # If conversion fails, try to format the raw value
                            raw_time = str(activity.moving_time)
                            if raw_time.isdigit():
                                seconds = int(raw_time)
                                hours = seconds // 3600
                                minutes = (seconds % 3600) // 60
                                if hours > 0:
                                    print(f"Moving Time: {hours}:{minutes:02d}:00")
                                else:
                                    print(f"Moving Time: {minutes:02d}:00")
                            else:
                                print(f"Moving Time: {raw_time}")
                    
                    # Handle average pace for runs
                    if str(activity.type).lower().find('run') >= 0 and hasattr(activity, 'average_speed'):
                        try:
                            speed_mps = float(activity.average_speed)
                            if speed_mps > 0:
                                pace_mins_per_km = (1000 / speed_mps) / 60
                                pace_mins = int(pace_mins_per_km)
                                pace_secs = int((pace_mins_per_km - pace_mins) * 60)
                                print(f"Avg Pace: {pace_mins}:{pace_secs:02d} /km")
                        except (ValueError, ZeroDivisionError):
                            pass
                    
                    # Handle elevation
                    if hasattr(activity, 'total_elevation_gain'):
                        try:
                            elevation = float(activity.total_elevation_gain)
                            print(f"Elevation Gain: {elevation:.0f} m")
                        except (ValueError, TypeError):
                            pass
                    
                    # Handle activity type specific details
                    if hasattr(activity, 'achievement_count') and activity.achievement_count:
                        print(f"Achievements: {activity.achievement_count}")
                    
                    if hasattr(activity, 'kudos_count'):
                        print(f"Kudos: {activity.kudos_count}")
                    
                    if hasattr(activity, 'comment_count'):
                        print(f"Comments: {activity.comment_count}")
                    
                    # Add workout type if available
                    if hasattr(activity, 'workout_type'):
                        workout_types = {
                            0: "Default",
                            1: "Race",
                            2: "Long Run",
                            3: "Workout"
                        }
                        workout_type = workout_types.get(activity.workout_type, "")
                        if workout_type:
                            print(f"Workout Type: {workout_type}")
                    
                    print("-" * 40)
                    
                except Exception as e:
                    print(f"Error processing activity: {str(e)}")
                    continue
            
            if not activity_found:
                print("\nNo activities found in the last 24 hours.")
                print("Try increasing the time range with:")
                print("fetcher.get_activities(days=7)  # for last 7 days")
                
        except Exception as e:
            print(f"Error fetching activities: {str(e)}")

def monitor_strava_data():
    fetcher = StravaDataFetcher()
    if fetcher.authenticate():
        while True:
            fetcher.get_activities()
            print("\nWaiting 5 minutes before next update...")
            time.sleep(300)  # Wait 5 minutes

if __name__ == "__main__":
    monitor_strava_data() 