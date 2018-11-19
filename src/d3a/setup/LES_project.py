import os
import csv
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.appliance.pv import PVAppliance
from d3a.models.const import ConstSettings
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.storage import StorageStrategy

from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.commercial_producer import CommercialStrategy


def csv_read_les_data(stedin_data_path):
    data_directory = stedin_data_path + '/separated_data_LES'
    number_of_households = len(os.listdir(data_directory))
    assert number_of_households is 28

    _stedin_dict = {}
    for house in os.listdir(data_directory):
        print('reading in house file from ', house)
        if house.endswith(".csv"):
            house_data_dict = {'DateTime': [], 'Home': [], 'BI': [], 'BO': [], 'DW': [], 'HP': [],
                               'PV': [], 'SE': [], 'SI': [], 'WM': [], 'proposition': []}
            with open(data_directory + '/' + house) as csv_file:
                data_file = csv.DictReader(csv_file, delimiter=',')
                for row in data_file:
                    for key in house_data_dict:
                        try:
                            data_point = float(row[key])
                        except ValueError:
                            data_point = str(row[key])

                        house_data_dict[key].append(data_point)
            house_id = float(house_data_dict['Home'][0])
            _stedin_dict[house_id] = house_data_dict
    print('finished reading in LES data into dictionary')

    return _stedin_dict


def get_setup(config):
    # one sided market
    ConstSettings.IAASettings.MARKET_TYPE = 1
    ConstSettings.StorageSettings.CAPACITY = 1
    grid_connection = True

    """ loading in the LES data dictionary """
    stedin_data_path = './src/d3a/resources/LES_resources'
    stedin_dict = csv_read_les_data(stedin_data_path)

    pv_profiles = {}
    heatpump_profiles = {}
    dishwasher_profiles = {}
    washingmachine_profiles = {}
    proposition = {}

    list_of_second_level_areas = []

    for house in stedin_dict:
        # house 1 id = 1 (not 0)
        # print(house, 'max HP', max(stedin_dict[house]['HP']))
        # print(house, 'max PV', max(stedin_dict[house]['PV']))

        # hack for taking only hours:minutes from the date-time-stamp
        pv_profiles[house] = \
            {stedin_dict[house]['DateTime'][i][11:16]:
             stedin_dict[house]['PV'][i]*3 for i in range(96)}
        heatpump_profiles[house] = \
            {stedin_dict[house]['DateTime'][i][11:16]:
             stedin_dict[house]['HP'][i] for i in range(96)}
        dishwasher_profiles[house] = \
            {stedin_dict[house]['DateTime'][i][11:16]:
             stedin_dict[house]['DW'][i] for i in range(96)}
        washingmachine_profiles[house] = \
            {stedin_dict[house]['DateTime'][i][11:16]:
             stedin_dict[house]['WM'][i] for i in range(96)}
        proposition[house] = stedin_dict[house]['proposition'][0]

        """     ZIH: PV & Battery
                BMZ: Only PV
                NOD: Only battery
                IHM: Neither PV, nor battery
        """
        if proposition[house] == 'ZIH':
            proposition[house] = {'PV': True, 'ESS': True}
        elif proposition[house] == 'BMZ':
            proposition[house] = {'PV': True, 'ESS': False}
        elif proposition[house] == 'NOD':
            proposition[house] = {'PV': False, 'ESS': True}
        elif proposition[house] == 'IHM':
            proposition[house] = {'PV': False, 'ESS': False}

    for house in stedin_dict:
        # LOADS
        house_device_list = [
            Area('H' + str(house) + ' HeatPump',
                 strategy=DefinedLoadStrategy(heatpump_profiles[house]),
                 appliance=SwitchableAppliance()),

            Area('H' + str(house) + ' DishWasher',
                 strategy=DefinedLoadStrategy(dishwasher_profiles[house]),
                 appliance=SwitchableAppliance()),

            Area('H' + str(house) + ' WashingMachine',
                 strategy=DefinedLoadStrategy(washingmachine_profiles[house]),
                 appliance=SwitchableAppliance())
        ]

        # PV
        if proposition[house]['PV'] is True:
            house_device_list.append(
                Area('H' + str(house) + ' PV',
                     strategy=PVUserProfileStrategy(power_profile=pv_profiles[house]),
                     appliance=PVAppliance())
            )

        # ESS
        if proposition[house]['ESS'] is True:
            house_device_list.append(
                Area('H' + str(house) + ' Storage',
                     strategy=StorageStrategy(initial_capacity_kWh=0.9),
                     appliance=SwitchableAppliance())
            )

        list_of_second_level_areas.append(
            Area('House ' + str(house), house_device_list)
        )

    if grid_connection:
        list_of_second_level_areas.append(
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance()
                 ),
        )

    stedin_les_community = Area('Grid', list_of_second_level_areas, config=config)
    return stedin_les_community
