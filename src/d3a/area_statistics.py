from collections import namedtuple, defaultdict
from statistics import mean
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.inter_area import InterAreaAgent
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import CellTowerLoadHoursStrategy
from d3a.models.strategy.facebook_device import CellTowerFacebookDeviceStrategy
from d3a.util import area_name_from_area_or_iaa_name, make_iaa_name


loads_avg_prices = namedtuple('loads_avg_prices', ['load', 'price'])


def get_area_type_string(area):
    if isinstance(area.strategy, CellTowerLoadHoursStrategy) or \
            isinstance(area.strategy, CellTowerFacebookDeviceStrategy):
        return "cell_tower"
    elif area.children is None:
        return "unknown"
    elif area.children != [] and all(child.children == [] for child in area.children):
        return "house"
    else:
        return "unknown"


def gather_area_loads_and_trade_prices(area, load_price_lists):
    for child in area.children:
        if child.children == [] and not \
                (isinstance(child.strategy, StorageStrategy) or
                 isinstance(child.strategy, PVStrategy) or
                 isinstance(child.strategy, InterAreaAgent) or
                 isinstance(child.strategy, NightStorageStrategy)):
            for slot, market in child.parent.past_markets.items():
                if slot.hour not in load_price_lists.keys():
                    load_price_lists[slot.hour] = loads_avg_prices(load=[], price=[])
                load_price_lists[slot.hour].load.append(market.traded_energy[child.name])
                trade_prices = [
                    t.offer.price / t.offer.energy
                    for t in market.trades
                    if t.buyer == child.name
                ]
                load_price_lists[slot.hour].price.extend(trade_prices)
        else:
            load_price_lists = gather_area_loads_and_trade_prices(child, load_price_lists)
    return load_price_lists


def export_cumulative_loads(area):
    load_price_lists = {}
    area_raw_results = gather_area_loads_and_trade_prices(area, load_price_lists)
    return [
        {
            "time": hour,
            "load": sum(load_price.load) if len(load_price.load) > 0 else 0,
            "price": mean(load_price.price) if len(load_price.price) > 0 else 0
        } for hour, load_price in area_raw_results.items()
    ]


def _is_house_node(area):
    return all(child.children == [] for child in area.children)


def _is_cell_tower_node(area):
    return isinstance(area.strategy, CellTowerLoadHoursStrategy) \
           or isinstance(area.strategy, CellTowerFacebookDeviceStrategy)


def _accumulate_cell_tower_trades(cell_tower, grid, accumulated_trades):
    accumulated_trades[cell_tower.name] = {
        "type": "cell_tower",
        "id": cell_tower.area_id,
        "produced": 0.0,
        "consumedFrom": defaultdict(int)
    }
    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            if trade.buyer == cell_tower.name:
                sell_id = area_name_from_area_or_iaa_name(trade.seller)
                accumulated_trades[cell_tower.name]["consumedFrom"][sell_id] += trade.offer.energy
    return accumulated_trades


def _accumulate_house_trades(house, grid, accumulated_trades):
    if house.name not in accumulated_trades:
        accumulated_trades[house.name] = {
            "type": "house",
            "id": house.area_id,
            "produced": 0.0,
            "consumedFrom": defaultdict(int)
        }
    house_IAA_name = make_iaa_name(house)
    child_names = [c.name for c in house.children]
    for slot, market in house.past_markets.items():
        for trade in market.trades:
            if area_name_from_area_or_iaa_name(trade.seller) in child_names and \
                    area_name_from_area_or_iaa_name(trade.buyer) in child_names:
                # House self-consumption trade
                accumulated_trades[house.name]["produced"] -= trade.offer.energy
                accumulated_trades[house.name]["consumedFrom"][house.name] += trade.offer.energy
            elif trade.buyer == house_IAA_name:
                accumulated_trades[house.name]["produced"] -= trade.offer.energy

    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            if trade.buyer == house_IAA_name:
                seller_id = area_name_from_area_or_iaa_name(trade.seller)
                accumulated_trades[house.name]["consumedFrom"][seller_id] += trade.offer.energy
    return accumulated_trades


def _accumulate_grid_trades(area, accumulated_trades):
    for child in area.children:
        if _is_cell_tower_node(child):
            accumulated_trades = _accumulate_cell_tower_trades(child, area, accumulated_trades)
        elif _is_house_node(child):
            accumulated_trades = _accumulate_house_trades(child, area, accumulated_trades)
        elif child.children == []:
            # Leaf node, no need for calculating cumulative trades, continue iteration
            continue
        else:
            accumulated_trades = _accumulate_grid_trades(child, accumulated_trades)
    return accumulated_trades


def area_name_to_id(area_name, grid):
    for child in grid.children:
        if child.name == area_name:
            return child.area_id
        elif child.children == []:
            continue
        else:
            res = area_name_to_id(area_name, child)
            if res is not None:
                return res
    return None


def _generate_produced_energy_entries(accumulated_trades):
    # Create produced energy results (negative axis)
    produced_energy = [{
        "x": area_name,
        "y": area_data["produced"],
        "target": area_name,
        "label": str(area_name) + " produced " + str(abs(area_data["produced"])) + " kWh"
    } for area_name, area_data in accumulated_trades.items()]
    return sorted(produced_energy, key=lambda a: a["x"])


def _generate_self_consumption_entries(accumulated_trades):
    # Create self consumed energy results (positive axis, first entries)
    self_consumed_energy = []
    for area_name, area_data in accumulated_trades.items():
        sc_energy = 0
        if area_name in area_data["consumedFrom"].keys():
            sc_energy = area_data["consumedFrom"].pop(area_name)
        self_consumed_energy.append({
            "x": area_name,
            "y": sc_energy,
            "target": area_name,
            "label": str(area_name) + " consumed " + str(sc_energy) + " kWh from " + str(area_name)
        })
    return sorted(self_consumed_energy, key=lambda a: a["x"])


def _generate_intraarea_consumption_entries(accumulated_trades):
    # Flatten consumedFrom entries from dictionaries to list of tuples, to be able to pop them
    # irregardless of their keys
    for area_name, area_data in accumulated_trades.items():
        area_data["consumedFrom"] = list(area_data["consumedFrom"].items())

    consumption_rows = []
    # Exhaust all consumedFrom entries from all houses
    while not all(not area_data["consumedFrom"] for k, area_data in accumulated_trades.items()):
        consumption_row = []
        for area_name in sorted(accumulated_trades.keys()):
            target_area = area_name
            consumption = 0
            if accumulated_trades[area_name]["consumedFrom"]:
                target_area, consumption = accumulated_trades[area_name]["consumedFrom"].pop()
            consumption_row.append({
                "x": area_name,
                "y": consumption,
                "target": target_area,
                "label": area_name + " consumed " + str(consumption) + " kWh from " + target_area
            })
        consumption_rows.append(sorted(consumption_row, key=lambda x: x["x"]))
    return consumption_rows


def export_cumulative_grid_trades(area):
    accumulated_trades = _accumulate_grid_trades(area, {})
    return {
        "unit": "kWh",
        "areas": sorted(accumulated_trades.keys()),
        "cumulative-grid-trades": [
            # Append first produced energy for all areas
            _generate_produced_energy_entries(accumulated_trades),
            # Then self consumption energy for all areas
            _generate_self_consumption_entries(accumulated_trades),
            # Then consumption entries for intra-house trades
            _generate_intraarea_consumption_entries(accumulated_trades)
        ]
    }
