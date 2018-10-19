from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.predefined_pv import d3a_path
import os

household_path = os.path.join(d3a_path, "resources/Household_Load.csv")
electrolyzer_path = os.path.join(d3a_path, "resources/Electrolyzer_Load.csv")
# price_path = os.path.join(d3a_path, "resources/Electricity_Prices.csv")
user_profile_path = os.path.join(d3a_path, "resources/PV_Profile.csv")


def get_setup(config):
    # config.read_market_maker_rate_2(price_path)
    area = Area(
        'Grid',
        [*[Area(
            f'Combined Loads {i}',
            [
                Area(f'Defined Combined Load {i}',
                     strategy=DefinedLoadStrategy(daily_load_profile=household_path,
                                                  max_energy_rate=30),
                     appliance=SwitchableAppliance()),
            ]) for i in range(1, 100)],
         Area('Electrolyser Load',
              [
                  Area('Electrolyser Load',
                       strategy=DefinedLoadStrategy(daily_load_profile=electrolyzer_path,
                                                    max_energy_rate=30),
                       appliance=PVAppliance()),
              ],
              ),

         Area('PV Power Plant',
              [
                  Area('PV Power Plant',
                       strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                      panel_count=1,
                                                      risk=0),
                       appliance=PVAppliance()),
              ],
              ),
         Area(
             'Combined Storage',
             [
                 Area('Defined Combined Storage',
                      strategy=StorageStrategy(initial_capacity=500000,
                                               battery_capacity=1000000,
                                               max_abs_battery_power=1000000,
                                               break_even=(7, 8),
                                               energy_rate_decrease_option=2,
                                               energy_rate_decrease_per_update=3),
                      appliance=SwitchableAppliance()),
             ]
         )
         ],
        config=config
    )
    return area
