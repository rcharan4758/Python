# Simplified AER Modeling Challenge  

## Overview
The CO2 emissions associated with an electricity grid are not constant over time -- based on the source of the energy,
there are periods throughout the day with much higher or lower associated emissions.  Many energy demands are actually
flexible with respect to when they are met.  For example, charging a battery may be flexible as long as the battery is
fully charged by a certain time. If such energy demands can actually be met dynamically, using dirty power can be 
reduced.  However, achieving this requires forecasting the "Marginal Operating Emissions Rate" (MOER) of the energy
grid, and, within the constraints of the energy demand, optimizing energy consumption with respect to this forecast.

This is a simulator that models the operation of a refrigerator connected to a smart plug (governing its energy 
consumption), with the goal of minimizing associated CO2 emissions.  The simulation runs for one month, during which 
time the algorithm governing when to turn the refrigerator on or off has access to a perfect 1-hour forecast of the 
MOER of the energy grid.  The algorithm may also use historical data as it becomes available.
Subject to the following constraints and parameters:
- The fridge must remain between 33 and 43 degrees F.
- The starting temperature of the fridge is 33 degrees F.
- When on, the fridge consumes 200 watts.  When off, it consumes no electricity.
- When on, the fridge cools at a rate of 10 degrees F per hour.  When off, it warms at a rate of 5 degrees F per hour.
- There is no penalty for the number of times the fridge turns on or off.

## Run the simulation

From the top-level directory:
```bash
python3 refrigerator_sim.py --best
```

This command runs the most optimal simulation. The simulation will take several minutes to complete (~4.5 minutes on 
Macbook with 2.4 GHz Quad-Core Intel Core i5). The result of the simulation can be found in `./output_data`, and 
includes a CSV file and corresponding plot with time on the x-axis. 
(`plots_zeroes_forecast_hist.pdf` and `sim_output_zeroes_forecast_hist.csv`)
The plot displays:
- The temperature of the refrigerator at each timestep, color-coded by whether the fridge was on or off at that time.
- The current MOER of the grid at each time. 
- Cumulative pounds of CO2 associated with the refrigerator’s energy consumption since the start of the simulation.

For additional command line options:
```bash
python3 refrigerator_sim.py --help
```
Which displays options for running simpler models. It is also possible to create a plot of the average MOERs at each 
time step (used to realize that the MOERs follow a daily pattern), and possible to control the number of timesteps that 
are executed, for speeding up testing rounds.

## (Best) Model Description
At a high level, the model chooses what to do (turn the fridge on or off) at each timestep by formulating the one-hour
forecast window as a linear programming problem and finding an optimal solution within the forecast window.  The first 
step of this optimal solution is then taken, at which time the simulation (and forecast horizon) has advanced one step.
However, if the MOER at that timestep is 0, the fridge simply turns on if possible (as long as it's not going to get
too cold, otherwise it turns off for that timestep.) The process is repeated with the next timestep and the shifted 
forecast window. The PuLP module is used to solve the LP problem.

Objective function to minimize:

    co2_emissions_proportional = (MOER_data_of_forecast)*(bitmap_of_fridge_status)
    
Subject to the following constraints, where `X_t` is the temperature of the fridge at time t and `S_t` is the on/off 
status of the fridge at time t:

    X_t+1 = X_t + cooling_rate * S_t + warming_rate * (1 - S_t)
    X_t >= 33
    X_t <= 43
   For all t.
    
Historical average data is gradually taken into account as it becomes available. As the simulation progresses, the
dataframe is updated with new historical averages for each timestep *based on that timestep's time of day*.  In other 
words, each timestep is associated with a particular time of day, and the historical averages for that "slot" in the day
are constructed from historical data occurring at the same time of day.

The historical average is used as the predicted MOER in order to extend the length of the forecast window in the linear 
programming problem, placing more emphasis on these historical predictions as the number of datapoints included in the 
average increases. Considering that the fridge can remain off for two hours when at its coldest setting (33 degrees),
it would probably benefit from forecasts extending at least two hours into the future (though perhaps not significantly
more than this...).  However, in order to keep the simulation run time below 5 minutes, the maximum achievable 
forecast window was only about 90 minutes into the future. 

## Summary of Results
Using no data, the fridge simply warms and cools like a thermostat: 26.7 lbs CO2 emitted

Using only a default response to the 0-MOER timesteps: 26.1 lbs CO2 emitted (~2.25% reduction)

Using 0-MOER defaults and the 1-hour accurate forecast: 20.7 lbs CO2 emitted (~22.5% reduction)

Using 0-MOER default, the 1-hour forecast and an extended lookahead with historical averages: 20.1 lbs CO2 emitted 
                                                                                                (~24.7% reduction)

## Future improvements

Given more time, there are several improvements I would make to the simulator:

The model:
- Experiment with greater timestamp granularity for decision-making.  I used the timestep size provided in the MOER data
(5 minutes).  However, a more granular dataset could be created and would potentially provide better results, though the
larger number of decision variables in the one-hour forecast window could quickly make this computationally infeasible.
- Experiment with the number of predicted MOERs included in the forecast window as historical averages.
  (Though this has already run up against computational time limits.)
- Experiment with the granularity at which averages are collected.  This model uses the same 5-minute granularity of
    a timestep, however it might make sense to use larger "buckets" such as one hour.
- Incorporate the first day’s pre-simulation data to populate the historical averages (just ran out of time)
- Consider other linear solvers to potentially improve performance.

The software:
- Unit tests!!  I tested functionality using a sanity-check no-data graph, and spot-checked functionality with print
statements, but proper unit tests with a small, fake dataframe should be implemented.
- Parameterize the model with a config file, making it easier to adjust parameters in one place, such as:
    - The input data path
    - The size of a timestep
    - The fridge params (valid range, starting temp, cooling and heating rates, wattage)
    - Lookahead duration
    - How far into the future to use historical average data
- Use this config design to create a driver program capable of running the simulation under many different parameter
assignments, searching for a more optimal model.
- Continue to seek out efficiencies where possible, since working with pandas (and Python in general) can be slowwww.
- Add timestamps to output filenames to avoid unintentionally overwriting.