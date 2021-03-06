Feature: Jira Issues Tests

   Scenario: D3ASIM-595, average trade rate should be constant for every market slot
     Given we have a scenario named jira/default_595
     And d3a is installed
     When we run the d3a simulation with jira.default_595 [24, 15, 15]
     Then average trade rate is constant for every market slot for all markets
     And there are no trades with the same seller and buyer name

#   Scenario: D3ASIM-645, storage should buy energy from commercial producer
#     Given we have a scenario named jira/default_645
#     And d3a is installed
#     When we run the d3a simulation with jira.default_645 [24, 15, 15]
#     Then storage buys energy from the commercial producer
#     And storage final SOC is 100%
#     And storage buys energy respecting the break even buy threshold

   Scenario: D3ASIM-662, IAA should always track offers back to its source
     Given we have a scenario named strategy_tests/home_cp_ess_load
     And d3a is installed
     When we run the d3a simulation with strategy_tests.home_cp_ess_load [24, 15, 15]
     Then on every market slot there should be matching trades on grid and house markets
     And there should be no unmatched loads

   @slow
   Scenario: D3ASIM-706, multi-day simulation for load and pv
     Given we have a scenario named default_3
     And d3a is installed
     When we run the d3a simulation with default_3 [72, 15, 60]
     Then pv produces the same energy on each corresponding time slot regardless of the day
     And all loads consume the same energy on each corresponding time slot regardless of the day
     And all loads adhere to the hours of day configuration

   Scenario: D3ASIM-780, Electrolyser does not report 0 soc on first market slot
     Given we have a scenario named jira/d3asim_780
     And d3a is installed
     When we run the d3a simulation with jira.d3asim_780 [24, 60, 60]
     Then there should be a reported SOC of 0.1 on the first market

   Scenario: D3ASIM-778, load reaches maximum price before the end of the market slot
     Given we have a scenario named jira/d3asim_778
     And d3a is installed
     When we run the simulation with setup file jira.d3asim_778 and parameters [24, 15, 15, 0, 1]
     Then there should be trades on all markets using the max load rate