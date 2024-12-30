from flask import Flask, render_template, request
import requests
import folium

app = Flask(__name__)

# OpenRouteService API Key
OR_SERVICE_API_KEY = '5b3ce3597851110001cf62481d7abc2708ad4856ad63639288ec805b'
# OpenWeatherMap API Key
WEATHER_API_KEY = '5938991ca3585919457c1147d4370f6d'
# TomTom Traffic API Key
TRAFFIC_API_KEY = 'u1xqxd7esr0PWotWPAiWCBP9GeH8botj'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_route', methods=['POST'])
def get_route():
    start_city = request.form['start']
    end_city = request.form['end']

    # Get Coordinates from City Names
    start_coords = geocode_city_to_coordinates(start_city)
    end_coords = geocode_city_to_coordinates(end_city)

    if start_coords and end_coords:
        # Get Route from OpenRouteService
        route, distance, estimated_time = get_route_from_openrouteservice(start_coords, end_coords)

        if route:
            # Generate Map with Folium
            map_path = generate_map(route)

            # Get Weather Data
            weather = get_weather_data(route)

            # Get Emissions Data
            emissions = get_emissions_data(route, distance)

            # Get Traffic Data
            traffic_condition, traffic_time = get_traffic_data(start_coords, end_coords)

            return render_template('index.html', route=route, distance=distance, weather=weather, emissions=emissions, map_path=map_path, traffic_condition=traffic_condition, traffic_time=traffic_time, estimated_time=estimated_time)
        else:
            return render_template('index.html', error="Could not find a route between the cities.")
    else:
        return render_template('index.html', error="Could not geocode one or both city names.")

def convert_minutes_to_hr_min(minutes):
    hours = minutes // 60
    minutes_remaining = minutes % 60
    return f"{int(hours)}h {int(minutes_remaining)}m"

def geocode_city_to_coordinates(city_name):
    # Geocoding API to get coordinates from city name
    geocode_url = f'https://api.openrouteservice.org/geocode/search?api_key={OR_SERVICE_API_KEY}&text={city_name}'

    try:
        response = requests.get(geocode_url)
        response.raise_for_status()  # Ensure request is successful
        data = response.json()

        if 'features' in data and len(data['features']) > 0:
            coordinates = data['features'][0]['geometry']['coordinates']
            return coordinates  # Returns [longitude, latitude]
        else:
            print(f"No coordinates found for {city_name}.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error in geocoding request: {e}")
        return None

def get_route_from_openrouteservice(start_coords, end_coords):
    # OpenRouteService API URL with coordinates
    url = f'https://api.openrouteservice.org/v2/directions/driving-car?api_key={OR_SERVICE_API_KEY}&start={start_coords[0]},{start_coords[1]}&end={end_coords[0]},{end_coords[1]}'

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if 'features' in data and len(data['features']) > 0:
            route = data['features'][0]['geometry']['coordinates']
            # Get the distance of the route in meters
            distance = data['features'][0]['properties']['segments'][0]['distance'] / 1000  # Convert to kilometers
            # Round distance to 2 decimal places
            distance = round(distance, 2)

            # Assume speed of cargo truck (in km/h)
            truck_speed = 70  # Example speed in km/h

            # Calculate estimated time to reach (in hours)
            estimated_time = distance / truck_speed  # Time in hours
            estimated_time_minutes = estimated_time * 60  # Convert to minutes

            # Convert time to hr:min format
            formatted_time = convert_minutes_to_hr_min(estimated_time_minutes)

            return route, distance, formatted_time
        else:
            print(f"No route found.")
            return None, None, None
    except requests.exceptions.RequestException as e:
        print(f"Error in route request: {e}")
        return None, None, None
    
def generate_map(route):
    # Create a map centered on the starting location
    start_lat, start_lon = route[0][1], route[0][0]  # Coordinates are in [lon, lat] format
    map_obj = folium.Map(location=[start_lat, start_lon], zoom_start=12)

    # Add the route to the map as a polyline
    folium.PolyLine(locations=[(lat, lon) for lon, lat in route], color="blue", weight=2.5, opacity=1).add_to(map_obj)

    # Save the map to an HTML file
    map_path = 'static/route_map.html'
    map_obj.save(map_path)
    return map_path

def get_weather_data(route):
    # Use OpenWeatherMap API to get weather data for the first location on the route
    lat, lon = route[0][1], route[0][0]
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}'

    try:
        response = requests.get(url)
        data = response.json()
        if data and 'weather' in data:
            weather = data['weather'][0]['description']
            temperature = data['main']['temp'] - 273.15  # Convert from Kelvin to Celsius
            humidity = data['main']['humidity']
            # Round temperature to 2 decimal places
            temperature = round(temperature, 2)
            return {"description": weather, "temperature": temperature, "humidity": humidity}
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error in weather request: {e}")
        return None
    
def get_emissions_data(route, distance):
    # Assuming a default emissions factor for a cargo truck (in grams per kilometer)
    emissions_factor = 200  # Placeholder value (grams of CO2 per kilometer)

    # Calculate total emissions based on the distance
    total_emissions = emissions_factor * distance  # Total emissions in grams
    total_emissions_kg = total_emissions / 1000  # Convert to kilograms for better readability
    # Round emissions to 2 decimal places
    total_emissions_kg = round(total_emissions_kg, 2)

    return {"co2": total_emissions_kg}  # Return emissions in kilograms

def get_traffic_data(start_coords, end_coords):
    # Get traffic data from TomTom Traffic API
    traffic_url = f'https://api.tomtom.com/traffic/services/4/incidentDetails?key={TRAFFIC_API_KEY}&bbox={start_coords[0]},{start_coords[1]},{end_coords[0]},{end_coords[1]}&extended=true'

    try:
        response = requests.get(traffic_url)
        response.raise_for_status()
        data = response.json()

        print("Traffic Data Response:", data)  # Debugging the response

        if data and 'incidents' in data:
            traffic_condition = 'Moderate'  # Default if no incidents
            estimated_time = 0  # Default estimated time

            # Analyze traffic incidents
            for incident in data['incidents']:
                if incident['severity'] == 'high':
                    traffic_condition = 'High'
                    estimated_time += incident.get('duration', 0)  # Add duration of incidents

            # Default to 1 hour estimation if no incidents
            estimated_time += 3600  # Add arbitrary 1 hour (3600 seconds)

            # Convert time to minutes and then to hr:min format
            estimated_time_minutes = estimated_time / 60
            formatted_time = convert_minutes_to_hr_min(estimated_time_minutes)

            return traffic_condition, formatted_time
        else:
            # If no incidents data, default to moderate traffic and a basic time estimate
            return 'Moderate', "1h 0m"  # Default moderate condition and 1-hour estimated time in hr:min format
    except requests.exceptions.RequestException as e:
        print(f"Error in traffic request: {e}")
        return 'Moderate', "1h 0m"  # Default to moderate traffic and 1-hour estimated time in case of error

if __name__ == '__main__':
    app.run(debug=True)
