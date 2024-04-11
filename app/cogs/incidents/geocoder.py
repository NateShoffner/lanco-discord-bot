import hashlib
import logging

import googlemaps
from lcwc.incident import Incident


class IncidentGeocoder:
    """Geocodes incidents using the Google Maps API"""

    def __init__(self, gmaps: googlemaps.Client) -> None:
        self.logger = logging.getLogger(__name__)
        self.client = gmaps
        self.cache = {}

    def get_absolute_address(self, incident: Incident) -> str:
        """Creates an absolute address from the given incident

        :param incident: The incident to create an absolute address from
        :return: The absolute address
        :rtype: str
        """
        if incident.intersection is None:
            self.logger.debug(f"No intersection found for incident: {incident}")
            return None

        addr = f"{incident.intersection}, {incident.municipality}, LANCASTER COUNTY, PA"
        return addr

    def get_coordinates(self, incident: Incident) -> tuple[float, float]:
        """Gets the coordinates of the given incident

        :param incident: The incident to get the coordinates of
        :return: The coordinates of the incident
        :rtype: tuple[float, float]
        """
        absolute_address = self.get_absolute_address(incident)

        if absolute_address is None:
            return None

        key = hashlib.sha1(absolute_address.encode("utf-8")).hexdigest()

        cached_coords = self.cache.get(key)
        if cached_coords:
            return cached_coords

        self.logger.debug(f"Geocoding address: {absolute_address}")

        try:
            geocode_result = self.client.geocode(absolute_address)

            if len(geocode_result) == 0:
                return None

            location = geocode_result[0]["geometry"]["location"]
            lat = location["lat"]
            lng = location["lng"]

            self.cache[key] = (lat, lng)
            return (lat, lng)
        except Exception as e:
            self.logger.error(f"Error geocoding address: {e}")
