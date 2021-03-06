"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.const import ConstSettings


def get_setup(config):
    # Two sided market
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.PVSettings.MIN_SELLING_RATE = 0
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.StorageSettings.MIN_BUYING_RATE = 0
    ConstSettings.StorageSettings.BREAK_EVEN_BUY = 29.9
    ConstSettings.StorageSettings.BREAK_EVEN_SELL = 30

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity_kWh=0.6,
                                                  break_even=(
                                                    ConstSettings.StorageSettings.BREAK_EVEN_BUY,
                                                    ConstSettings.StorageSettings.BREAK_EVEN_SELL)
                                                  ),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV',
                         strategy=PVStrategy(4, 0),
                         appliance=PVAppliance()
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
