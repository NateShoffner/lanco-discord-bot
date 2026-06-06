import asyncio
import logging
import os
import random
from cmath import cos, sin
from urllib.parse import urlencode

import aiohttp
import requests

from .models import Coordinates, GeoGuesserLocation, Mode


class LocationUtils:
    def __init__(self, gmaps):
        self.gmaps = gmaps
        self.logger = logging.getLogger(__name__)

    def get_location_label(self, coords: Coordinates) -> str:
        """Returns the best human-readable label for the given coordinates via reverse geocode."""
        try:
            results = self.gmaps.reverse_geocode((coords.lat, coords.lng))
            if not results:
                raise ValueError("No results")

            # prefer intersection type
            for result in results:
                if "intersection" in result.get("types", []):
                    return result["formatted_address"].split(",")[0]

            # require a route (street name) — city-only results are not useful
            components = results[0].get("address_components", [])
            route = next(
                (c["short_name"] for c in components if "route" in c.get("types", [])),
                None,
            )
            if not route:
                return f"{coords.lat:.5f}, {coords.lng:.5f}"

            locality = next(
                (
                    c["short_name"]
                    for c in components
                    if "locality" in c.get("types", [])
                ),
                None,
            )
            return f"{route}, {locality}" if locality else route
        except Exception as e:
            self.logger.warning(
                f"Reverse geocode failed for {coords.lat},{coords.lng}: {e}"
            )
            return f"{coords.lat:.5f}, {coords.lng:.5f}"

    def get_coordinates_from_location(self, location_name: str) -> Coordinates:
        """Returns the coordinates of the location"""
        # TODO cache location names to avoid unnecessary API calls
        geocode_result = self.gmaps.geocode(
            location_name
        )  # called from a thread via session.handle_guess
        if len(geocode_result) > 0:
            lat = geocode_result[0]["geometry"]["location"]["lat"]
            lng = geocode_result[0]["geometry"]["location"]["lng"]
            return Coordinates(lat, lng)
        else:
            self.logger.error(f"Error: {location_name} not found")
            return None

    def get_street_view_url(self, coords: Coordinates) -> str:
        """Returns a street view image URL for the given coordinates"""
        base_url = "https://maps.googleapis.com/maps/api/streetview?"
        params = {
            "location": f"{coords.lat},{coords.lng}",
            "size": "800x450",
            "fov": "90",
            "heading": "random",  # Set the heading to 'random' for a random direction
            "pitch": "0",  # Set the pitch to '0' for a horizontal view
            "key": os.getenv("GMAPS_API_KEY"),
        }

        full_url = base_url + urlencode(params)
        return full_url

    async def get_random_streetview_image(self, coords: Coordinates) -> str:
        """Returns a random street view image URL for the given coordinates"""
        url = self.get_street_view_url(coords)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return url
                else:
                    self.logger.error(f"Error: {resp.status}")
                    return None

    def get_random_subcoordinate_from_bounds(bounding_box: tuple) -> tuple:
        """Returns a random coordinate within the bounding box"""
        min_lat, max_lat, min_lng, max_lng = bounding_box
        random_lat = random.uniform(min_lat, max_lat)
        random_lng = random.uniform(min_lng, max_lng)
        return random_lat, random_lng

    def get_random_subcoordinate_from_center(
        self, center_coord: tuple[float, float], radius_in_meters: int, num_points=1
    ) -> list:
        """Generates random coordinates within a given radius from a center point"""
        random_coordinates = []

        for _ in range(num_points):
            # Generate a random angle in radians
            angle = random.uniform(0, 2 * 3.141592653589793)

            # Generate a random distance within the radius
            random_distance = random.uniform(0, radius_in_meters)

            # Calculate the new coordinates
            dx = random_distance * (radius_in_meters / 111320.0) * cos(angle)
            dy = random_distance * (radius_in_meters / 111320.0) * sin(angle)

            new_latitude = center_coord[0] + (dy / 111320.0)
            new_longitude = center_coord[1] + (dx / (111320.0 * cos(center_coord[0])))

            random_coordinates.append((new_latitude, new_longitude))

        return random_coordinates

    def get_geoguesser_locations_sync(
        self, mode: Mode, num_locations: int
    ) -> list[GeoGuesserLocation]:
        """Synchronous version — call via asyncio.to_thread from async contexts."""
        locations = []
        for i in range(num_locations):
            location = self.get_geoguesser_location_sync(mode)
            locations.append(location)
            self.logger.info(
                f"Generated location {i + 1}/{num_locations} for '{mode.name}': {location.label or location.road_coords}"
            )
        return locations

    async def get_geoguesser_locations(
        self, mode: Mode, num_locations: int
    ) -> list[GeoGuesserLocation]:
        return await asyncio.to_thread(
            self.get_geoguesser_locations_sync, mode, num_locations
        )

    async def get_geoguesser_location(self, mode: Mode) -> GeoGuesserLocation:
        return await asyncio.to_thread(self.get_geoguesser_location_sync, mode)

    def get_geoguesser_location_sync(self, mode: Mode) -> GeoGuesserLocation:
        """Returns a geoguesser location within the bounding box"""
        road = None
        while not road:
            lat, lng = self.get_random_subcoordinate_from_center(
                mode.center, mode.radius, 1
            )[0]

            if isinstance(lat, complex):
                lat = lat.real
            if isinstance(lng, complex):
                lng = lng.real

            initial_location = Coordinates(lat, lng)
            roads = self.gmaps.snap_to_roads(initial_location.to_tuple())
            if len(roads) > 0:
                road = roads[0]
            else:
                self.logger.error("Error: No roads found, trying again...")

        road_coords = Coordinates(
            road["location"]["latitude"], road["location"]["longitude"]
        )

        # use metadata API to check coverage without downloading the image
        metadata_url = (
            f"https://maps.googleapis.com/maps/api/streetview/metadata"
            f"?location={road_coords.lat},{road_coords.lng}"
            f"&key={os.getenv('GMAPS_API_KEY')}"
        )
        meta_resp = requests.get(metadata_url)
        if meta_resp.status_code != 200 or meta_resp.json().get("status") != "OK":
            self.logger.error(
                f"No street view imagery for {road_coords}, trying again..."
            )
            return self.get_geoguesser_location_sync(mode)

        label = self.get_location_label(road_coords)
        return GeoGuesserLocation(initial_location, road_coords, label=label)
