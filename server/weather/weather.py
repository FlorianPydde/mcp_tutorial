"""
Weather MCP Server

A Model Context Protocol server that provides weather information tools
using the National Weather Service API. Follows MCP SDK best practices
for server implementation, error handling, and transport configuration.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize logging with proper configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server with proper naming and configuration
mcp = FastMCP(
    name="weather-service",
    dependencies=["httpx"],  # Explicit dependencies for deployment
)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> Dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling and logging.

    Args:
        url: The NWS API endpoint URL to request

    Returns:
        JSON response data if successful, None if failed

    Raises:
        None - errors are logged and None is returned for graceful degradation
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Making request to NWS API: {url}")
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully retrieved data from {url}")
            return data

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
        return None
    except httpx.TimeoutException:
        logger.error(f"Timeout requesting {url}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error requesting {url}: {e}")
        return None


def format_alert(feature: Dict[str, Any]) -> str:
    """Format an alert feature into a readable string.

    Args:
        feature: Alert feature from NWS API response

    Returns:
        Formatted alert string with event, area, severity, description and instructions
    """
    props = feature.get("properties", {})
    event = props.get("event", "Unknown Event")
    area = props.get("areaDesc", "Unknown Area")
    severity = props.get("severity", "Unknown Severity")
    description = props.get("description", "No description available")
    instruction = props.get("instruction", "No specific instructions provided")

    return (
        f"Event: {event}\n"
        f"Area: {area}\n"
        f"Severity: {severity}\n"
        f"Description: {description}\n"
        f"Instructions: {instruction}"
    )


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Retrieves active weather alerts from the National Weather Service
    for the specified state code. Provides comprehensive alert information
    including event type, affected areas, severity level, and instructions.

    Args:
        state: Two-letter US state code (e.g., 'CA', 'NY', 'TX')
               Must be a valid US state or territory abbreviation

    Returns:
        Formatted string containing all active alerts for the state,
        or a message indicating no alerts or an error occurred

    Example:
        get_alerts("CA") -> Returns current alerts for California
    """
    # Validate state code format
    if not state or len(state) != 2:
        return (
            "Error: Please provide a valid two-letter US state code (e.g., 'CA', 'NY')"
        )

    state = state.upper().strip()

    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    logger.info(f"Fetching alerts for state: {state}")

    data = await make_nws_request(url)

    if not data:
        return f"Unable to fetch weather alerts for state '{state}'. Please check the state code and try again."

    features = data.get("features", [])
    if not features:
        return f"No active weather alerts found for {state}."

    try:
        alerts = [format_alert(feature) for feature in features]
        result = "\n" + "=" * 50 + "\n".join(alerts)
        logger.info(f"Successfully formatted {len(alerts)} alerts for {state}")
        return result
    except Exception as e:
        logger.error(f"Error formatting alerts for {state}: {e}")
        return f"Error processing weather alerts for {state}. Please try again."


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location using coordinates.

    Retrieves detailed weather forecast from the National Weather Service
    for the specified geographic coordinates. Provides multi-day forecast
    with temperature, wind, and detailed conditions.

    Args:
        latitude: Latitude coordinate (decimal degrees, -90 to 90)
                 Example: 37.7749 for San Francisco
        longitude: Longitude coordinate (decimal degrees, -180 to 180)
                  Example: -122.4194 for San Francisco

    Returns:
        Formatted string containing detailed weather forecast periods,
        or an error message if the request fails

    Example:
        get_forecast(37.7749, -122.4194) -> Returns forecast for San Francisco
    """
    # Validate coordinates
    if not (-90 <= latitude <= 90):
        return f"Error: Latitude must be between -90 and 90 degrees. Got: {latitude}"

    if not (-180 <= longitude <= 180):
        return (
            f"Error: Longitude must be between -180 and 180 degrees. Got: {longitude}"
        )

    logger.info(f"Fetching forecast for coordinates: {latitude}, {longitude}")

    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return (
            f"Unable to fetch forecast data for location ({latitude}, {longitude}). "
            "This location may be outside the US or territories covered by NWS."
        )

    try:
        # Extract forecast URL from points response
        properties = points_data.get("properties", {})
        forecast_url = properties.get("forecast")

        if not forecast_url:
            return "Error: Unable to determine forecast URL for this location."

        logger.info(f"Requesting detailed forecast from: {forecast_url}")
        forecast_data = await make_nws_request(forecast_url)

        if not forecast_data:
            return "Unable to fetch detailed forecast for this location."

        # Format the forecast periods
        properties = forecast_data.get("properties", {})
        periods = properties.get("periods", [])

        if not periods:
            return "No forecast periods available for this location."

        forecasts = []
        for period in periods[:5]:  # Show next 5 periods
            name = period.get("name", "Unknown Period")
            temp = period.get("temperature", "Unknown")
            temp_unit = period.get("temperatureUnit", "°F")
            wind_speed = period.get("windSpeed", "Unknown")
            wind_dir = period.get("windDirection", "Unknown")
            detailed = period.get("detailedForecast", "No detailed forecast available")

            forecast = (
                f"{name}:\n"
                f"  Temperature: {temp} {temp_unit}\n"
                f"  Wind: {wind_speed} {wind_dir}\n"
                f"  Forecast: {detailed}"
            )
            forecasts.append(forecast)

        result = "\n" + "=" * 50 + "\n".join(forecasts)
        logger.info(f"Successfully formatted forecast with {len(forecasts)} periods")
        return result

    except Exception as e:
        logger.error(f"Error processing forecast data: {e}")
        return f"Error processing forecast for location ({latitude}, {longitude}). Please try again."


@mcp.tool()
async def get_current_conditions(latitude: float, longitude: float) -> str:
    """Get current weather conditions for a location.

    Provides current weather observations from the nearest weather station
    to the specified coordinates.

    Args:
        latitude: Latitude coordinate (decimal degrees, -90 to 90)
        longitude: Longitude coordinate (decimal degrees, -180 to 180)

    Returns:
        Current weather conditions including temperature, humidity, wind, etc.
    """
    # Validate coordinates
    if not (-90 <= latitude <= 90):
        return f"Error: Latitude must be between -90 and 90 degrees. Got: {latitude}"

    if not (-180 <= longitude <= 180):
        return (
            f"Error: Longitude must be between -180 and 180 degrees. Got: {longitude}"
        )

    logger.info(f"Fetching current conditions for coordinates: {latitude}, {longitude}")

    # Get the nearest weather station
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return (
            f"Unable to fetch weather station data for location ({latitude}, {longitude}). "
            "This location may be outside the US or territories covered by NWS."
        )

    try:
        properties = points_data.get("properties", {})
        observation_stations_url = properties.get("observationStations")

        if not observation_stations_url:
            return "No weather observation stations found for this location."

        # Get the list of observation stations
        stations_data = await make_nws_request(observation_stations_url)
        if not stations_data:
            return "Unable to fetch weather station information."

        features = stations_data.get("features", [])
        if not features:
            return "No weather stations available for this location."

        # Get current conditions from the first available station
        station_id = features[0].get("properties", {}).get("stationIdentifier")
        if not station_id:
            return "Unable to identify weather station."

        conditions_url = f"{NWS_API_BASE}/stations/{station_id}/observations/latest"
        conditions_data = await make_nws_request(conditions_url)

        if not conditions_data:
            return "Unable to fetch current weather conditions."

        # Format current conditions
        props = conditions_data.get("properties", {})

        # Extract temperature
        temp_data = props.get("temperature", {})
        temp_c = temp_data.get("value")
        temp_f = None
        if temp_c is not None:
            temp_f = (temp_c * 9 / 5) + 32

        # Extract other conditions
        humidity = props.get("relativeHumidity", {}).get("value")
        wind_speed = props.get("windSpeed", {}).get("value")  # m/s
        wind_dir = props.get("windDirection", {}).get("value")  # degrees
        description = props.get("textDescription", "No description available")
        timestamp = props.get("timestamp", "Unknown time")

        # Format wind speed to mph if available
        wind_mph = None
        if wind_speed is not None:
            wind_mph = wind_speed * 2.237  # Convert m/s to mph

        # Format wind direction
        wind_dir_text = ""
        if wind_dir is not None:
            directions = [
                "N",
                "NNE",
                "NE",
                "ENE",
                "E",
                "ESE",
                "SE",
                "SSE",
                "S",
                "SSW",
                "SW",
                "WSW",
                "W",
                "WNW",
                "NW",
                "NNW",
            ]
            index = round(wind_dir / 22.5) % 16
            wind_dir_text = directions[index]

        result = "Current Weather Conditions:\n"
        result += f"Station: {station_id}\n"
        result += f"Time: {timestamp}\n"
        result += f"Description: {description}\n"

        if temp_f is not None:
            result += f"Temperature: {temp_f:.1f}°F ({temp_c:.1f}°C)\n"

        if humidity is not None:
            result += f"Humidity: {humidity:.0f}%\n"

        if wind_mph is not None and wind_dir_text:
            result += f"Wind: {wind_mph:.1f} mph {wind_dir_text}\n"
        elif wind_mph is not None:
            result += f"Wind Speed: {wind_mph:.1f} mph\n"

        logger.info(
            f"Successfully retrieved current conditions for {latitude}, {longitude}"
        )
        return result

    except Exception as e:
        logger.error(f"Error processing current conditions data: {e}")
        return f"Error retrieving current conditions for location ({latitude}, {longitude}). Please try again."


def get_service_info() -> str:
    """Provide information about the weather service capabilities.

    Returns static information about what this MCP server can do.
    Resources are used for contextual data that LLMs can reference.
    """
    return """Weather MCP Server Information

This server provides weather information tools using the National Weather Service API.

Available Tools:
- get_alerts(state): Get active weather alerts for a US state
- get_forecast(latitude, longitude): Get detailed weather forecast for coordinates  
- get_current_conditions(latitude, longitude): Get current weather observations

Supported Areas:
- United States and territories covered by the National Weather Service
- Requires valid US state codes (2-letter abbreviations)
- Coordinates must be within NWS coverage area

Data Source:
- National Weather Service (weather.gov) API
- Real-time data updated regularly
- No API key required (public service)

Usage Notes:
- State codes should be 2-letter abbreviations (e.g., 'CA', 'NY', 'TX')
- Coordinates should be in decimal degrees format
- Service covers US, Puerto Rico, Guam, and other US territories
"""


def get_state_codes() -> str:
    """Provide a reference of US state codes for weather alerts.

    Returns a comprehensive list of valid state codes that can be used
    with the get_alerts tool.
    """
    return """US State and Territory Codes for Weather Alerts

States:
AL - Alabama          AK - Alaska           AZ - Arizona          AR - Arkansas
CA - California       CO - Colorado         CT - Connecticut      DE - Delaware  
FL - Florida          GA - Georgia          HI - Hawaii           ID - Idaho
IL - Illinois         IN - Indiana          IA - Iowa             KS - Kansas
KY - Kentucky         LA - Louisiana        ME - Maine            MD - Maryland
MA - Massachusetts    MI - Michigan         MN - Minnesota        MS - Mississippi
MO - Missouri         MT - Montana          NE - Nebraska         NV - Nevada
NH - New Hampshire    NJ - New Jersey       NM - New Mexico       NY - New York
NC - North Carolina   ND - North Dakota     OH - Ohio             OK - Oklahoma
OR - Oregon           PA - Pennsylvania     RI - Rhode Island     SC - South Carolina
SD - South Dakota     TN - Tennessee        TX - Texas            UT - Utah
VT - Vermont          VA - Virginia         WA - Washington       WV - West Virginia
WI - Wisconsin        WY - Wyoming

Territories:
AS - American Samoa   DC - District of Columbia   GU - Guam
MP - Northern Mariana Islands   PR - Puerto Rico   VI - US Virgin Islands

Usage: get_alerts("CA") for California alerts, get_alerts("PR") for Puerto Rico alerts
"""


if __name__ == "__main__":
    import sys

    import uvicorn

    # Support multiple transports following MCP SDK patterns
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"

    logger.info(f"Starting weather MCP server with {transport} transport")

    if (
        transport == "streamable-http"
    ):  # Streamable HTTP transport (recommended for production)
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))

        logger.info(f"Starting MCP weather server (Streamable HTTP) on {host}:{port}")
        logger.info("MCP endpoint will be available at /mcp")

        # Use uvicorn with FastMCP app directly (production pattern)
        starlette_app = mcp.streamable_http_app()

        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Run with proper async context
        import asyncio

        asyncio.run(server.serve())

    else:
        # stdio transport for local/desktop integration
        logger.info("Starting MCP weather server with stdio transport")
        logger.info("Server ready for stdio communication")
        mcp.run(transport="stdio")
