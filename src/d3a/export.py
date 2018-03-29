import csv
import json
import logging
import pathlib

import pandas as pd
import os
import plotly as py
import plotly.graph_objs as go

from d3a.models.market import Trade
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy

_log = logging.getLogger(__name__)


def export(root_area, path, subdir):
    """Export all data of the finished simulation in one CSV file per area."""
    try:
        directory = pathlib.Path(path or "~/d3a-simulation", subdir).expanduser()
        directory.mkdir(exist_ok=True, parents=True)
    except Exception as ex:
        _log.error("Could not open directory for csv exports: %s" % str(ex))
        return
    _export_area_with_children(root_area, directory)
    _export_overview(root_area, directory)

    _unmatch_loads(directory, 'relative', 'Devices Un-matched Loads', 'Time',
                   'Energy (kWh)', 'Devices_unmatch_loads.html')

    _energy_trade_partner(directory, 'buyer', 'Cell Tower', 'seller',
                          'Cell Tower Energy Suppliers', 'Cell_Tower_Energy_Suppliers.html')
    _ess_history(directory, 'relative', 'ESS Energy Trade', 'Time',
                 'Energy (kWh)', 'ESS_Trade.html')
    _house_etrade_history(directory, 'relative', 'Time',
                          'Energy (kWh)')


def _export_area_with_children(area, directory):
    if area.children:
        subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
        subdirectory.mkdir(exist_ok=True, parents=True)
        for child in area.children:
            _export_area_with_children(child, subdirectory)
    _export_area_flat(area, directory)
    if area.children:
        _export_area_energy(area, directory)


def _file_path(directory, slug):
    file_name = ("%s.csv" % slug).replace(' ', '_')
    return directory.joinpath(file_name).as_posix()


class ExportData:
    def __init__(self, area):
        self.area = area

    @staticmethod
    def create(area):
        return ExportUpperLevelData(area) if area.children else ExportLeafData(area)


class ExportUpperLevelData(ExportData):
    def __init__(self, area):
        super(ExportUpperLevelData, self).__init__(area)

    def labels(self):
        return ['slot',
                'avg trade price [EUR]',
                'min trade price [EUR]',
                'max trade price [EUR]',
                '# trades',
                'total energy traded [kWh]',
                'total trade volume [EUR]']

    def rows(self):
        markets = self.area.past_markets
        return [self._row(slot, markets[slot]) for slot in markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_trade_price,
                market.min_trade_price,
                market.max_trade_price,
                len(market.trades),
                sum(trade.offer.energy for trade in market.trades),
                sum(trade.offer.price for trade in market.trades)]


class ExportLeafData(ExportData):
    def __init__(self, area):
        super(ExportLeafData, self).__init__(area)

    def labels(self):
        return ['slot', 'energy traded [kWh]'] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, FridgeStrategy):
            return ['temperature [°C]']
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            return ['bought [kWh]', 'sold [kWh]', 'energy balance [kWh]', 'offered [kWh]',
                    'used [kWh]', 'charge [%]']
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            return ['desired energy [kWh]', 'deficit [kWh]']
        elif isinstance(self.area.strategy, PVStrategy):
            return ['produced to trade [kWh]', 'not sold [kWh]', 'forecast / generation [kWh]']
        return []

    def rows(self):
        markets = self.area.parent.past_markets
        return [self._row(slot, markets[slot]) for slot in markets]

    def _traded(self, market):
        return market.traded_energy[self.area.name]

    def _row(self, slot, market):
        return [slot, self._traded(market)] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, FridgeStrategy):
            return [self.area.strategy.temp_history[slot]]
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            s = self.area.strategy.state
            return [market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.charge_history_kWh[slot],
                    s.offered_history[slot],
                    s.used_history[slot],
                    s.charge_history[slot]]
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            desired = self.area.strategy.state.desired_energy[slot] / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = market.actual_energy_agg.get(self.area.name, 0)
            return [produced,
                    round(produced - self._traded(market), 4),
                    self.area.strategy.energy_production_forecast_kWh[slot] *
                    self.area.strategy.panel_count
                    ]
        return []


def _export_area_flat(area, directory):
    data = ExportData.create(area)
    rows = data.rows()
    if rows:
        try:
            with open(_file_path(directory, area.slug), 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(data.labels())
                for row in rows:
                    writer.writerow(row)
        except Exception as ex:
            _log.error("Could not export area data: %s" % str(ex))


def _export_area_energy(area, directory):
    try:
        with open(_file_path(directory, "{}-trades".format(area.slug)), 'w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(("slot",) + Trade._csv_fields())
            for slot, market in area.past_markets.items():
                for trade in market.trades:
                    writer.writerow((slot, ) + trade._to_csv())
    except OSError:
        _log.exception("Could not export area trades")


def _export_overview(root_area, directory):
    markets = root_area.past_markets
    overview = {
        'avg_trade_price_history': [markets[slot].avg_trade_price for slot in markets]
    }
    try:
        directory.joinpath("overview.json").write_text(json.dumps(overview, indent=2))
    except Exception as ex:
        _log.error("Error when writing overview file: %s" % str(ex))


class DataSets:
    def __init__(self, path):
        self.path = path
        self.dataset = pd.read_csv(path)


class UnmatchLoads(DataSets):
    def __init__(self, path, key):
        self.key = key
        self.umHours = dict()
        super(UnmatchLoads, self).__init__(path)

    def um_time(self):
        try:
            self.dataset[self.key]
        except KeyError:
            print('key not found')
        else:
            for de in range(len(self.dataset[self.key])):
                if (self.dataset[self.key][de] != 0):
                    self.umHours[self.dataset['slot'][de]] = self.dataset[self.key][de]

    def plot_bar_graph(barmode, title, xtitle, ytitle, data, iname):
        layout = go.Layout(
            barmode=barmode,
            title=title,
            yaxis=dict(
                title=ytitle
            ),
            xaxis=dict(
                title=xtitle
            )
        )

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)


# Un-met Loads
def _unmatch_loads(path, barmode, title, xtitle, ytitle, iname):
    data = list()
    key = 'deficit [kWh]'
    os.chdir(path)
    sub_file = sorted(next(os.walk('grid'))[1])
    for i in range(len(sub_file)):
        gl = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-general-load.csv')
        ll = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-lighting.csv')
        tv = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-tv.csv')

        if(os.path.isfile(gl)):
            higl = UnmatchLoads(gl, key)
            higl.um_time()
            traceigl = go.Bar(x=list(higl.umHours.keys()),
                              y=list(higl.umHours.values()),
                              name='House{}-GL'.format(i+1))
            data.append(traceigl)
        if(os.path.isfile(ll)):
            hill = UnmatchLoads(ll, key)
            hill.um_time()
            traceill = go.Bar(x=list(hill.umHours.keys()),
                              y=list(hill.umHours.values()),
                              name='House{}-LL'.format(i+1))
            data.append(traceill)
        if(os.path.isfile(tv)):
            hitv = UnmatchLoads(tv, key)
            hitv.um_time()
            traceitv = go.Bar(x=list(hitv.umHours.keys()),
                              y=list(hitv.umHours.values()),
                              name='House{}-TV'.format(i+1))
            data.append(traceitv)
    plot_dir = str(path) + '/plot'
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    os.chdir(plot_dir)

    UnmatchLoads.plot_bar_graph(barmode, title, xtitle, ytitle, data, iname)


class TradeHistory(DataSets):
    def __init__(self, path, key):
        self.key = key
        self.trade_history = dict()
        super(TradeHistory, self).__init__(path)
# kvalue=cell tower
# kseller=x,y,z

    def arrange_data(self, kbuyer, kseller):
        try:
            self.dataset[self.key]
        except KeyError:
            print('key not found')
        else:
            for de in range(len(self.dataset[self.key])):
                self.trade_history.setdefault(self.dataset[kseller][de], int(0))
            for de in range(len(self.dataset[self.key])):
                if (self.dataset[self.key][de] == kbuyer):
                    self.trade_history[self.dataset[kseller][de]] += 1

    def plot_pie_chart(self, title, iname):
        fig = {
            "data": [
                {
                    "values": list(),
                    "labels": list(),
                    "type": "pie"
                }],
            "layout": {
                "title": title,
            }
        }
        for key, value in self.trade_history.items():
            fig["data"][0]["values"].append(value)
            fig["data"][0]["labels"].append(key)

        py.offline.plot(fig, filename=iname, auto_open=False)


# Energy Trading Partner
def _energy_trade_partner(path, key, buyer, seller, title, iname):
    os.chdir(path)
    gt = str('grid-trades.csv')

    if(os.path.isfile(gt)):
        higt = TradeHistory(gt, key)
        higt.arrange_data(buyer, seller)

    plot_dir = str(path) + '/plot'
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    os.chdir(plot_dir)

    higt.plot_pie_chart(title, iname)


# ESS Trade History
def _ess_history(path, barmode, title, xtitle, ytitle, iname):
    data = list()
    key = 'energy traded [kWh]'
    os.chdir(path)
    sub_file = sorted(next(os.walk('grid'))[1])
    for i in range(len(sub_file)):
        ss1 = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-storage1.csv')
        ss2 = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-storage2.csv')

        if (os.path.isfile(ss1)):
            hiss1 = UnmatchLoads(ss1, key)
            hiss1.um_time()
            traceiss1 = go.Bar(x=list(hiss1.umHours.keys()),
                               y=list(hiss1.umHours.values()),
                               name='House{0}-Storage1'.format(i + 1))
            data.append(traceiss1)
        if (os.path.isfile(ss2)):
            hiss2 = UnmatchLoads(ss2, key)
            hiss2.um_time()
            traceiss2 = go.Bar(x=list(hiss2.umHours.keys()),
                               y=list(hiss2.umHours.values()),
                               name='House{0}-Storage2'.format(i + 1))
            data.append(traceiss2)

    plot_dir = str(path) + '/plot'
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    os.chdir(plot_dir)

    UnmatchLoads.plot_bar_graph(barmode, title, xtitle, ytitle, data, iname)


# Energy Profile of House
def _house_etrade_history(path, barmode, xtitle, ytitle):
    data = list()
    key = 'energy traded [kWh]'
    os.chdir(path)
    sub_file = sorted(next(os.walk('grid'))[1])
    for i in range(len(sub_file)):
        gl = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-general-load.csv')
        ll = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-lighting.csv')
        tv = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-tv.csv')
        ss1 = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-storage1.csv')
        ss2 = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-storage2.csv')
        pv = str('grid/' + sub_file[i] + '/h' + str(i + 1) + '-pv.csv')
        iname = str('Energy Profile of House{}.html'.format(i + 1))
        title = str('Energy Profile of House{}'.format(i + 1))
        if(os.path.isfile(gl)):
            higl = UnmatchLoads(gl, key)
            higl.um_time()
            traceigl = go.Bar(x=list(higl.umHours.keys()),
                              y=list(higl.umHours.values()),
                              name='House{}-GL'.format(i+1))
            data.append(traceigl)
        if(os.path.isfile(ll)):
            hill = UnmatchLoads(ll, key)
            hill.um_time()
            traceill = go.Bar(x=list(hill.umHours.keys()),
                              y=list(hill.umHours.values()),
                              name='House{}-LL'.format(i+1))
            data.append(traceill)
        if(os.path.isfile(tv)):
            hitv = UnmatchLoads(tv, key)
            hitv.um_time()
            traceitv = go.Bar(x=list(hitv.umHours.keys()),
                              y=list(hitv.umHours.values()),
                              name='House{}-TV'.format(i+1))
            data.append(traceitv)
        if (os.path.isfile(ss1)):
            hiss1 = UnmatchLoads(ss1, key)
            hiss1.um_time()
            traceiss1 = go.Bar(x=list(hiss1.umHours.keys()),
                               y=list(hiss1.umHours.values()),
                               name='House{0}-Storage1'.format(i + 1))
            data.append(traceiss1)
        if (os.path.isfile(ss2)):
            hiss2 = UnmatchLoads(ss2, key)
            hiss2.um_time()
            traceiss2 = go.Bar(x=list(hiss2.umHours.keys()),
                               y=list(hiss2.umHours.values()),
                               name='House{0}-Storage2'.format(i + 1))
            data.append(traceiss2)
        if (os.path.isfile(pv)):
            hipv = UnmatchLoads(pv, key)
            hipv.um_time()
            traceipv = go.Bar(x=list(hipv.umHours.keys()), y=list(hipv.umHours.values()),
                              name='House{0}-PV'.format(i + 1))
            data.append(traceipv)
        plot_dir = str(path) + '/plot'
        if not os.path.exists(plot_dir):
            os.makedirs(plot_dir)
        os.chdir(plot_dir)

        UnmatchLoads.plot_bar_graph(barmode, title, xtitle, ytitle, data, iname)
        os.chdir('..')
        data = list()
