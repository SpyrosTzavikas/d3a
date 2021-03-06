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
import csv
import logging
import pathlib
import os
import plotly as py
import plotly.graph_objs as go
import pendulum
import shutil

from d3a.constants import TIME_ZONE
from d3a.models.market.market_structures import Trade, BalancingTrade, Bid, Offer, BalancingOffer
from d3a.models.area import Area
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints


_log = logging.getLogger(__name__)

ENERGY_BUYER_SIGN_PLOTS = 1
ENERGY_SELLER_SIGN_PLOTS = -1 * ENERGY_BUYER_SIGN_PLOTS


def mkdir_from_str(directory: str, exist_ok=True, parents=True):
    out_dir = pathlib.Path(directory)
    out_dir.mkdir(exist_ok=exist_ok, parents=parents)
    return out_dir


class ExportAndPlot:

    def __init__(self, root_area: Area, path: str, subdir: str):
        self.area = root_area
        self.export_data = FileExportEndpoints(root_area)
        try:
            if path is not None:
                path = os.path.abspath(path)
            self.directory = pathlib.Path(path or "~/d3a-simulation", subdir).expanduser()
            mkdir_from_str(str(self.directory.mkdir))
        except Exception as ex:
            _log.error("Could not open directory for csv exports: %s" % str(ex))
            return

        self.plot_dir = os.path.join(self.directory, 'plot')
        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        self.export()

    @staticmethod
    def _file_path(directory: dir, slug: str):
        file_name = ("%s.csv" % slug).replace(' ', '_')
        return directory.joinpath(file_name).as_posix()

    def export(self):
        """Wrapping function, executes all export and plotting functions"""

        self._export_area_with_children(self.area, self.directory)
        self.plot_trade_partner_cell_tower(self.area, self.plot_dir)
        self.plot_energy_profile(self.area, self.plot_dir)
        self.plot_all_unmatched_loads()
        self.plot_avg_trade_price(self.area, self.plot_dir)
        self.plot_ess_soc_history(self.area, self.plot_dir)

        self.move_root_plot_folder()

    def move_root_plot_folder(self):
        """
        Removes "grid" folder in self.plot_dir
        """
        old_dir = os.path.join(self.plot_dir, self.area.slug)
        if not os.path.isdir(old_dir):
            _log.error("PLOT ERROR: No plots were generated for {} under {}".
                       format(self.area.slug, self.plot_dir))
            return
        source = os.listdir(old_dir)
        for si in source:
            shutil.move(os.path.join(old_dir, si), self.plot_dir)
        shutil.rmtree(old_dir)

    def _export_area_with_children(self, area: Area, directory: dir):
        """
        Uses the FileExportEndpoints object and writes them to csv files
        Runs _export_area_energy and _export_area_stats_csv_file
        """
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
            subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self._export_area_with_children(child, subdirectory)
        self._export_area_stats_csv_file(area, directory, balancing=False)
        self._export_area_stats_csv_file(area, directory, balancing=True)
        if area.children:
            self._export_trade_csv_files(area, directory, balancing=False)
            self._export_trade_csv_files(area, directory, balancing=True)
            self._export_area_offers_bids_csv_files(area, directory, "offers",
                                                    Offer, "offers", area.past_markets)
            self._export_area_offers_bids_csv_files(area, directory, "bids",
                                                    Bid, "bids", area.past_markets)
            self._export_area_offers_bids_csv_files(area, directory, "balancing-offers",
                                                    BalancingOffer, "offers",
                                                    area.past_balancing_markets)

    def _export_area_offers_bids_csv_files(self, area, directory, file_suffix,
                                           offer_type, market_member, past_markets):
        """
        Exports files containing individual offers, bids or balancing offers
        (*-bids/offers/balancing-offers.csv files)
        return: dict[out_keys]
        """
        file_path = self._file_path(directory, f"{area.slug}-{file_suffix}")
        labels = ("slot",) + offer_type._csv_fields()
        try:
            with open(file_path, 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(labels)
                for market in past_markets:
                    for offer in getattr(market, market_member).values():
                        row = (market.time_slot,) + offer._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area balancing offers")

    def _export_trade_csv_files(self, area: Area, directory: dir, balancing: bool = False):
        """
        Exports files containing individual trades  (*-trades.csv  files)
        return: dict[out_keys]
        """

        if balancing:
            file_path = self._file_path(directory, "{}-balancing-trades".format(area.slug))
            labels = ("slot",) + BalancingTrade._csv_fields()
            past_markets = area.past_balancing_markets
        else:
            file_path = self._file_path(directory, "{}-trades".format(area.slug))
            labels = ("slot",) + Trade._csv_fields()
            past_markets = area.past_markets

        try:
            with open(file_path, 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(labels)
                for market in past_markets:
                    for trade in market.trades:
                        row = (market.time_slot,) + trade._to_csv()
                        writer.writerow(row)
        except OSError:
            _log.exception("Could not export area trades")

    def _export_area_stats_csv_file(self, area: Area, directory: dir, balancing: bool):
        """
        Exports stats (*.csv files)
        """

        area_name = area.slug
        if balancing:
            area_name += "-balancing"
        data = self.export_data.generate_market_export_data(area, balancing)
        rows = data.rows()
        if not rows:
            return

        try:
            with open(self._file_path(directory, area_name), 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(data.labels())
                for row in rows:
                    writer.writerow(row)
        except Exception as ex:
            _log.error("Could not export area data: %s" % str(ex))

    def plot_trade_partner_cell_tower(self, area: Area, subdir: str):
        """
        Wrapper for _plot_trade_partner_cell_tower
        """
        key = "cell-tower"
        new_subdir = os.path.join(subdir, area.slug)
        for child in area.children:
            if child.slug == key:
                self._plot_trade_partner_cell_tower(child.slug, subdir)
            if child.children:
                self.plot_trade_partner_cell_tower(child, new_subdir)

    def _plot_trade_partner_cell_tower(self, load: str, plot_dir: str):
        """
        Plots trade partner pie graph for the sell tower.
        """
        higt = TradeHistory(self.export_data.buyer_trades, load)
        higt.arrange_data()
        mkdir_from_str(plot_dir)
        higt.plot_pie_chart("Energy Trade Partners for {}".format(load),
                            os.path.join(plot_dir, "energy_trade_partner_{}.html".format(load)))

    def plot_energy_profile(self, area: Area, subdir: str):
        """
        Wrapper for _plot_energy_profile
        """

        new_subdir = os.path.join(subdir, area.slug)
        self._plot_energy_profile(new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot_energy_profile(child, new_subdir)

    def _plot_energy_profile(self, subdir: str, market_name: str):
        """
        Plots history of energy trades
        """
        data = list()
        barmode = "relative"
        xtitle = 'Time'
        ytitle = 'Energy [kWh]'
        key = 'energy'
        title = 'Energy Trade Profile of {}'.format(market_name)
        data.extend(self._plot_energy_graph(self.export_data.traded_energy,
                                            market_name, "sold_energy_lists",
                                            "-seller", key, ENERGY_SELLER_SIGN_PLOTS))
        data.extend(self._plot_energy_graph(self.export_data.traded_energy,
                                            market_name, "bought_energy_lists",
                                            "-buyer", key, ENERGY_BUYER_SIGN_PLOTS))
        data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                            market_name, "sold_energy_lists",
                                            "-balancing-seller", key, ENERGY_SELLER_SIGN_PLOTS))
        data.extend(self._plot_energy_graph(self.export_data.balancing_traded_energy,
                                            market_name, "bought_energy_lists",
                                            "-balancing-buyer", key, ENERGY_BUYER_SIGN_PLOTS))
        if len(data) == 0:
            return
        if all([len(da.y) == 0 for da in data]):
            return

        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir,
                                   'energy_profile_{}.html'.format(market_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _plot_energy_graph(self, trades, market_name, agent, agent_label, key, scale_value):
        internal_data = []
        for trader in trades[market_name][agent].keys():

            graph_obj = BarGraph(trades[market_name][agent][trader], key)
            graph_obj.graph_value(scale_value=scale_value)
            data_obj = go.Bar(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=trader + agent_label)
            internal_data.append(data_obj)
        return internal_data

    def plot_all_unmatched_loads(self):
        """
        Plot unmatched loads of all loads in the configuration into one plot
        """
        unmatched_key = 'deficit [kWh]'
        data = list()
        root_name = self.area.slug
        title = 'Unmatched Loads for all devices in {}'.format(root_name)
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        barmode = 'stack'
        load_list = [child_key for child_key in self.export_data.plot_stats.keys()
                     if unmatched_key in self.export_data.plot_stats[child_key].keys()]

        for li in load_list:
            graph_obj = BarGraph(self.export_data.plot_stats[li], unmatched_key)
            if sum(graph_obj.dataset[unmatched_key]) < 1e-10:
                continue
            graph_obj.graph_value()
            data_obj = go.Bar(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=li)
            data.append(data_obj)
        if len(data) == 0:
            return
        plot_dir = os.path.join(self.plot_dir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'unmatched_loads_{}.html'.format(root_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_ess_soc_history(self, area, subdir):
        """
        Wrapper for _plot_ess_soc_history.
        """

        storage_key = 'charge [%]'
        new_subdir = os.path.join(subdir, area.slug)
        storage_list = [child.slug for child in area.children
                        if storage_key in self.export_data.plot_stats[child.slug].keys()]
        if storage_list is not []:
            self._plot_ess_soc_history(storage_list, new_subdir, area.slug)
        for child in area.children:
            if child.children:
                self.plot_ess_soc_history(child, new_subdir)

    def _plot_ess_soc_history(self, storage_list: list, subdir: str, root_name: str):
        """
        Plots ess soc for each knot in the hierarchy
        """

        storage_key = 'charge [%]'
        data = list()
        barmode = "relative"
        title = 'ESS SOC ({})'.format(root_name)
        xtitle = 'Time'
        ytitle = 'Charge [%]'

        for si in storage_list:
            graph_obj = BarGraph(self.export_data.plot_stats[si], storage_key)
            graph_obj.graph_value()
            data_obj = go.Scatter(x=list(graph_obj.umHours.keys()),
                                  y=list(graph_obj.umHours.values()),
                                  name=si)
            data.append(data_obj)
        if len(data) == 0:
            return
        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'ess_soc_history_{}.html'.format(root_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_avg_trade_price(self, area, subdir):
        """
        Wrapper for _plot_avg_trade_rate
        """
        if area.children:
            area_list = [area.slug]
            if area.parent:
                area_list.append(area.parent.slug)
            area_list += [ci.slug for ci in area.children]
            new_subdir = os.path.join(subdir, area.slug)
            self._plot_avg_trade_price(area_list, new_subdir)
            for child in area.children:
                self.plot_avg_trade_price(child, new_subdir)

    def _plot_avg_trade_price(self, area_list: list, subdir: str):
        """
        Plots average trade for the specified level of the hierarchy
        """
        data = list()
        barmode = 'stack'
        xtitle = "Time"
        ytitle = "Rate [ct./kWh]"
        key = 'avg trade rate [ct./kWh]'
        title = 'Average Trade Price {}'.format(area_list[0])
        for area_name in area_list:
            data.append(
                self._plot_avg_trade_graph(self.export_data.plot_stats,
                                           area_name, key, area_name)
            )
            if self.export_data.plot_balancing_stats[area_name.lower()] is not None:
                area_name_balancing = area_name.lower() + "-demand-balancing-trades"
                data.append(self._plot_avg_trade_graph(
                    self.export_data.plot_balancing_stats, area_name,
                    'avg demand balancing trade rate [ct./kWh]',
                    area_name_balancing)
                )
                area_name_balancing = area_name.lower() + "-supply-balancing-trades"
                data.append(self._plot_avg_trade_graph(
                    self.export_data.plot_balancing_stats, area_name,
                    'avg supply balancing trade rate [ct./kWh]',
                    area_name_balancing)
                )

        if all([len(da.y) == 0 for da in data]):
            return
        plot_dir = os.path.join(self.plot_dir, subdir)
        mkdir_from_str(plot_dir)
        output_file = os.path.join(plot_dir, 'average_trade_price_{}.html'.format(area_list[0]))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _plot_avg_trade_graph(self, stats, area_name, key, label):
        graph_obj = BarGraph(stats[area_name.lower()], key)
        graph_obj.graph_value()
        data_obj = go.Scatter(x=list(graph_obj.umHours.keys()),
                              y=list(graph_obj.umHours.values()),
                              name=label.lower())
        return data_obj


class BarGraph:
    def __init__(self, dataset: dict, key: str):
        self.key = key
        self.dataset = dataset
        self.umHours = dict()

    def graph_value(self, scale_value=1):
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for de in range(len(self.dataset[self.key])):
                if self.dataset[self.key][de] != 0:
                    if self.dataset[self.key][de] == "-":
                        self.umHours[self.dataset['slot'][de]] = 0.0
                    else:
                        self.umHours[self.dataset['slot'][de]] = \
                            round(self.dataset[self.key][de], 5) * scale_value

    @staticmethod
    def modify_time_axis(data: dict, title: str):
        """
        Changes timezone of pendulum x-values to 'UTC' and determines the list of days
        in order to return the time_range for the plot
        """
        day_set = set()
        for di in range(len(data)):
            time_list = data[di]["x"]
            for ti in time_list:
                day_set.add(pendulum.datetime(ti.year, ti.month, ti.day, tz=TIME_ZONE))

        day_list = sorted(list(day_set))
        if len(day_list) == 0:
            raise ValueError("There is no time information in plot {}".format(title))

        start_time = pendulum.datetime(day_list[0].year, day_list[0].month, day_list[0].day,
                                       0, 0, 0, tz=TIME_ZONE)
        end_time = pendulum.datetime(day_list[-1].year, day_list[-1].month, day_list[-1].day,
                                     23, 59, 59, tz=TIME_ZONE)

        return [start_time, end_time], data

    @classmethod
    def plot_bar_graph(cls, barmode: str, title: str, xtitle: str, ytitle: str, data, iname: str):
        try:
            time_range, data = cls.modify_time_axis(data, title)
        except ValueError:
            return

        layout = go.Layout(
            barmode=barmode,
            title=title,
            yaxis=dict(
                title=ytitle
            ),
            xaxis=dict(
                title=xtitle,
                range=time_range
            ),
            font=dict(
                size=16
            ),
            showlegend=True
        )

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)


class TradeHistory:
    def __init__(self, dataset: dict, key: str):
        self.key = key
        self.dataset = dataset
        self.trade_history = dict()

    def arrange_data(self):
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for ii, ki in enumerate(self.dataset[self.key]["seller"]):
                if ki in self.trade_history.keys():
                    self.trade_history[ki] += abs(self.dataset[self.key]["energy [kWh]"][ii])
                else:
                    self.trade_history[ki] = abs(self.dataset[self.key]["energy [kWh]"][ii])

    def plot_pie_chart(self, title, filename):
        fig = {
            "data": [
                {
                    "values": list(),
                    "labels": list(),
                    "type": "pie"
                }],
            "layout": {
                "title": title,
                "font": {"size": 16
                         }
            }
        }
        for key, value in self.trade_history.items():
            fig["data"][0]["values"].append(value)
            fig["data"][0]["labels"].append(key)

        py.offline.plot(fig, filename=filename, auto_open=False)
