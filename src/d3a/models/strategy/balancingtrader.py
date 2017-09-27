from collections import defaultdict
from typing import Dict  # noqa

from d3a.exceptions import MarketException
from d3a.models.market import Market  # noqa
from d3a.models.strategy.base import BaseStrategy


class BalancingtraderStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.next_market = None
        self.bought_energy = defaultdict(tuple)  # type: Dict[Market, tuple(float, float)]

    def event_activate(self):
        pass

    def event_tick(self, *, area):
        pass

    def event_market_cycle(self):
        pass

    def event_trade(self, *, market, trade):
        # FIXME area will change if Balancing trader becomes part of the IAA
        if trade.buyer == self.owner.name:
            return

        if market.area == self.area:
            needed_balancing_energy = sum(t.offer.energy * 0.1 for t in market.trades)
            total_trading_volume = 0
            # Since we're buying the offers with more than the wanted 10% volume of the
            # initial trade we might want to skip buying sometimes - If we have more
            # than 15% of the total trade volume as balancing energy
            for t in market.trades:
                if t.buyer != self.owner.name:
                    total_trading_volume += t.offer.energy

            # If there are no values in the dict for the key "markets"
            # it raises an value error
            try:
                bought_energy, spent_money = self.bought_energy[market]
            except ValueError:
                bought_energy, spent_money = 0, 0

            if bought_energy > (total_trading_volume * 0.15):
                return
            else:
                needed_balancing_energy -= bought_energy

            for cheapest_offer in market.cheapest_offers:
                if cheapest_offer.energy < needed_balancing_energy:
                    try:
                        self.accept_offer(offer=cheapest_offer, market=market)
                        self.bought_energy[market] = (bought_energy + cheapest_offer.energy,
                                                      spent_money + cheapest_offer.price)
                        needed_balancing_energy -= cheapest_offer.energy
                        continue
                    except MarketException:
                        # Offer already gone etc., try next one.
                        self.log.exception("Couldn't buy - co < nbe")
                        continue

                if (((total_trading_volume * 0.15) - bought_energy) >
                        cheapest_offer.energy > needed_balancing_energy):
                    try:
                        self.accept_offer(offer=cheapest_offer, market=market)
                        self.bought_energy[market] = (bought_energy + cheapest_offer.energy,
                                                      spent_money + cheapest_offer.price)
                        return
                    except MarketException:
                        # Offer already gone etc., try next one.
                        self.log.exception("Couldn't buy - co > nbe")
                        continue

                else:
                    continue
