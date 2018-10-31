from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.predefined_pv import d3a_path
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance
import os

user_profile_path = os.path.join(d3a_path, "resources/PV_Profile_5kWp.csv")
user_profile_path1 = os.path.join(d3a_path, "resources/House1.csv")
user_profile_path2 = os.path.join(d3a_path, "resources/House2.csv")
user_profile_path3 = os.path.join(d3a_path, "resources/House3.csv")
user_profile_path4 = os.path.join(d3a_path, "resources/House4.csv")
user_profile_path5 = os.path.join(d3a_path, "resources/House5.csv")


def get_setup(config):
    area = Area(
        'Grid', [
            Area('House 1', children=[
                Area(f'Load House 1',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path1,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
                Area('H1 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0), appliance=PVAppliance()),
                Area('H1 Storage1', strategy=StorageStrategy(battery_capacity_kWh=0.6),
                     appliance=SwitchableAppliance()),
            ]),
            Area('House 2', children=[
                Area(f'Load House 2',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path2,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
                Area('H2 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0), appliance=PVAppliance()),
                Area('H2 Storage1', strategy=StorageStrategy(battery_capacity_kWh=0.6),
                     appliance=SwitchableAppliance()),
            ]),
            Area('House 3', children=[
                Area(f'Load House 3',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path3,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
                Area('H3 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0), appliance=PVAppliance()),
                Area('H3 Storage1', strategy=StorageStrategy(battery_capacity_kWh=0.6),
                     appliance=SwitchableAppliance()),
            ]),
            Area('House 4', children=[
                Area(f'Load House 4',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path4,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
                Area('H4 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0), appliance=PVAppliance()),
                Area('H4 Storage1', strategy=StorageStrategy(battery_capacity_kWh=0.6),
                     appliance=SwitchableAppliance()),
            ]),
            Area('House 5', children=[
                Area(f'Load House 5',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path5,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
                Area('H5 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0), appliance=PVAppliance()),
                Area('H5 Storage1', strategy=StorageStrategy(battery_capacity_kWh=0.6),
                     appliance=SwitchableAppliance()),

            ]),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(energy_rate=29),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
