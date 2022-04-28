class Refrigerator:
    """A class representing the refrigerator/smart plug object."""
    MAX_TEMP = 43  # Fahrenheit
    MIN_TEMP = 33
    WATTAGE = 200
    WARMING_RATE = 5/60  # degrees/minute
    COOLING_RATE = -10/60  # degrees/minute

    def __init__(self):
        self.on = False
        self.current_temp = self.MIN_TEMP  # simulation begins at coldest temp
        self.current_timestamp = 0  # minutes

    def _current_rate_temp_change(self):
        """Returns the current rate of temperature change for the refrigerator, which depends on its on/off status."""
        if self.on:
            return self.COOLING_RATE
        else:
            return self.WARMING_RATE

    def expected_temp(self, timestamp):
        """
        Returns the expected temperature of the refrigerator at the provided timestep, based on current
        temperature and assuming no change to current on/off status.

        :param timestamp: The timestep at which to determine the refrigerator's temperature
        :return: The expected temperature of the fridge at the given timestep
        """
        elapsed = timestamp - self.current_timestamp
        return self.current_temp + (elapsed * self._current_rate_temp_change())

    def turn_on(self):
        self.on = True

    def turn_off(self):
        self.on = False
