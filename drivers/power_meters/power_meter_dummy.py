from . import power_meter as pm

class DummyPowerMeter(pm.PowerMeter):
    '''
    A dummy power metre that can be used for testing purposes.

    Args:
        dummy_power_value_W (int): The dummy power value in [W]
            that will be read when reading the power.
        dummy_wavelength_value_m (int): The dummy wavelength value in
            in [m] that will be read when reading the power.

    Attributes:
        dummy_power_value_W (int): The dummy power value in [W]
            that will be read when reading the power.
        dummy_wavelength_value_m (int): The dummy wavelength value in
            in [m] that will be read when reading the power.
    '''
    def __init__(self, dummy_power_value_W=-1., dummy_wavelength_value_m=-1.):
        self.dummy_power_value_W = dummy_power_value_W
        self.dummy_wavelength_value_m = dummy_wavelength_value_m

    def _get_power_W(self):
        return self.dummy_power_value_W

    def get_wavelength_m(self):
        return self.dummy_wavelength_value_m

    def set_wavelength_m(self, wavelength_m):
        pass
    
