from pulp import *
import numpy as np
import time
from refrigerator import Refrigerator
from visualizer import Visualizer


class Simulator:
    """A simulator for modeling a simplified Automated Emissions Reduction (AER) algorithm applied to a smart plug."""

    def __init__(self, moer_data, output_dir, num_timesteps):
        """
        :param moer_data: a pandas dataframe containing the initial simulation data
        :param output_dir: a path to the directory for outputting simulation artifacts
        :param num_timesteps: the number of timesteps (data rows) to process per simulation
        """
        self.visualizer = Visualizer(self)
        self.fridge = Refrigerator()
        self.historicals = {}
        self.total_lbs_co2 = 0
        self.mins_per_timestep = 5  # size of one timestep in minutes
        self.lookahead_window = int(60 / self.mins_per_timestep)  # timesteps in one hour
        self.current_time = 0
        self.output_dir = output_dir
        self.number_timesteps_to_process = num_timesteps
        self.data = moer_data
        self.np_moer_vector = self.data["MOER"].to_numpy()
        self._add_synthetic_fields_to_dataframe()

    def run(self, *, use_zeroes=False, use_forecast=False, use_hist=False):
        """
        Top-level simulation method. Makes a decision for fridge on/off at each timestep of the simulation,
        and writes resulting data to .csv file, then invokes visualizer to create and save a plot of the
        resulting data.

        :param use_zeroes: whether to make default decision to turn on (if possible) in timesteps with a MOER value of 0
        :param use_forecast: whether to incorporate the 1-hr forecast window into decision making.
        :param use_hist: whether to extend the forecast window using historical averages as they become available.
        """
        if use_hist and not use_forecast:
            raise Exception("If historical averages are being used, forecast window must be too.")

        start_time = time.time()
        output_filename = self._get_output_filename(use_zeroes, use_forecast, use_hist)
        self._prepare_new_simulation(output_filename)

        for timestep in range(self.number_timesteps_to_process):
            made_decision = False
            # the expected temp if the fridge continues in its current state (on/off) for another timestep
            expected_temp = self.fridge.expected_temp(self.current_time + self.mins_per_timestep)

            if use_zeroes:
                if self.np_moer_vector[timestep] == 0:
                    if expected_temp > self.fridge.MIN_TEMP:
                        self.fridge.turn_on()  # if the MOERS are free and the fridge isn't too cold, turn on!
                    else:
                        self.fridge.turn_off()  # we HAVE to turn off, getting too cold
                    made_decision = True

            if use_forecast and not made_decision:
                decision = self._get_next_decision_with_lp(timestep, use_historicals=use_hist)  # <-- all the action
                if decision == 0:
                    self.fridge.turn_off()
                else:
                    self.fridge.turn_on()
                made_decision = True

            if not made_decision:  # case using no data at all
                if expected_temp <= self.fridge.MIN_TEMP:
                    self.fridge.turn_off()
                elif expected_temp >= self.fridge.MAX_TEMP:
                    self.fridge.turn_on()

            # write csv row for this timestep
            self._generate_output_row(timestep)

            # update simulator state for next timestep
            self.fridge.current_temp = self.fridge.expected_temp(self.current_time + self.mins_per_timestep)
            self.current_time += self.mins_per_timestep
            self.fridge.current_timestamp = self.current_time

            # update historicals dictionary and dataframe row (even if not using them, in case plot_moer_avgs needs)
            self._update_historical_avgs(timestep)

        self.outfile.close()
        self._print_co2_emissions()
        self._print_sim_run_time(start_time, output_filename.lstrip("sim_output_"))
        print("\nGenerating matplotlib plots (~30s)...")
        self.visualizer.plot(output_filename)
        return output_filename  # to link the output with this run, used by plot_avg_moers

    def plot_avg_moers(self):
        """Generates a plot of the average MOER data for a given time of day, across duration of simulation."""
        output_filename = self.run()  # don't care about the actual simulation here
        self.visualizer.plot_avg_moers(output_filename)
        return

    def _get_next_decision_with_lp(self, start_timestep, use_historicals=False):
        """
        Generates and returns the decision that the refrigerator should make (be off or on) for this timestep.
        The decision is made by solving a linear programming problem that seeks to minimize CO2 production in the
        forecast window, subject to the temperature constraints in which the refrigerator must remain.
        The first step of the optimal solution is returned.

        :param start_timestep: the index of this timestep in the simulation
        :param use_historicals: whether or not to attempt to extend the forecast window using historical averages
        :return: 0 if the refrigerator should be off, 1 if the refrigerator should be on
        """
        model = LpProblem("CO2_Minimization_Problem", LpMinimize)
        moer_vector = self.np_moer_vector[start_timestep: start_timestep + self.lookahead_window]

        if use_historicals:
            # extend the forecast window using historical averages as predicted MOERs
            # extend the forecast window in proportion to the quality of the average (number datapoints used to calc)
            timeslotID = self.data['timeslotID'][start_timestep]
            if timeslotID in self.historicals:
                num_datapoints_in_avg = self.historicals[timeslotID][1]
            else:
                num_datapoints_in_avg = 0

            hist_lookahead_window = min(num_datapoints_in_avg, 6)  # computationally feasible

            moer_vector_hist_avg = np.array(self.data['hist_avg_moer_at_time']
                                            [start_timestep + self.lookahead_window:
                                             start_timestep + self.lookahead_window + hist_lookahead_window])
            moer_vector = np.concatenate((moer_vector, moer_vector_hist_avg))

        variable_suffixes = [str(i) for i in range(moer_vector.size)]
        # s for status (on/off)
        decision_variables = LpVariable.matrix("s", variable_suffixes, cat="Binary")
        status_vector = np.array(decision_variables)

        # Set up objective function
        obj_func = lpSum(status_vector * moer_vector)
        model += obj_func

        # Set up constraints
        temp_variables = LpVariable.matrix("t", variable_suffixes, cat="Continuous")
        for i in range(moer_vector.size - 1):
            model += temp_variables[i + 1] == temp_variables[i] + \
                     self.fridge.COOLING_RATE * self.mins_per_timestep * status_vector[i] + \
                     self.fridge.WARMING_RATE * self.mins_per_timestep * (1 - status_vector[i])
            model += temp_variables[i + 1] <= self.fridge.MAX_TEMP
            model += temp_variables[i + 1] >= self.fridge.MIN_TEMP
        model += temp_variables[0] == self.fridge.current_temp  # starting temp of fridge

        model.solve(PULP_CBC_CMD(msg=False))

        return model.variablesDict()['s_0'].value()

    def _add_synthetic_fields_to_dataframe(self):
        """
        Adds several calculated fields to the initial data table (self.data) created from the .csv file:
            - timeslotID: the unique time of day of this timestep, encoded in hhmm (hour hour minute minute) format
            - hist_avg_moer_at_time: the running averge MOER for this particular time of day, as of this point in the
                                    simulation
        """
        # add "timeslotID" - to tie a timestamp to its relative time of day
        process_timestamp = lambda timestamp: "".join(timestamp.split(" ")[1].split(":")[:2])
        self.data['timeslotID'] = self.data['timestamp'].apply(process_timestamp)

        # create an empty historical avg column
        self.data['hist_avg_moer_at_time'] = 0
        return

    def _get_output_filename(self, use_zeroes, use_forecast, use_hist):
        """Generates a descriptive name for simulation output data."""
        output_suffix = ''
        if use_zeroes:
            output_suffix += '_zeroes'
        if use_forecast:
            output_suffix += '_forecast'
        if use_hist:
            output_suffix += '_hist'
        if output_suffix == '':
            output_suffix = '_no_data'
        return self.output_dir.rstrip("/") + "/" + "sim_output" + output_suffix + ".csv"

    def _prepare_new_simulation(self, output_filename):
        """
        Resets dynamic fields and collections in Simulator object in preparation for a fresh simulation.

        :param output_filename: The name of the file that data will be written to during this simulation.
        """
        self.fridge = Refrigerator()
        self.historicals = {}
        self.current_time = 0
        self.total_lbs_co2 = 0
        self.data['hist_avg_moer_at_time'] = 0
        self.outfile = open(output_filename, 'w')
        # write CSV headers
        self.outfile.write("time,fridge_temp,fridge_on,moer,lbs_co2,avg_moer_at_time\n")
        print("\nRunning simulation ({})...".format(output_filename.lstrip("sim_output_")))

    def _update_historical_avgs(self, timestep):
        """
        Incorporates the MOER data at this timestep into the running average MOER for all corresponding (same
        time of day) timesteps.

        :param timestep: the index of the current timestep in the simulation data
        """
        timeslotID = self.data.iloc[timestep]['timeslotID']
        moer = self.data.iloc[timestep]['MOER']
        avg = moer
        count = 1
        if timeslotID in self.historicals:
            old_avg = self.historicals[timeslotID][0]
            count = self.historicals[timeslotID][1]
            avg = (count * old_avg + moer) / (count + 1)
            count += 1
        # Update running average for this time of day
        self.historicals[timeslotID] = (avg, count)

        # Update new historical average to NEXT equivalent timeslot.  As long as the forecast window doesn't exceed 288
        # timesteps (currently maxing out at 18), then we only ever have to update the one value at a time.
        # Future values set at this time would be overwritten anyway.  Past values don't matter.
        timesteps_per_day = 288
        next_corresponding_timeslot = timestep + timesteps_per_day
        if next_corresponding_timeslot < self.number_timesteps_to_process:
            self.data.iloc[next_corresponding_timeslot, self.data.columns.get_loc('hist_avg_moer_at_time')] = avg
        return

    def _generate_output_row(self, timestep):
        """
        Writes a single row of data to output csv file.

        :param timestep: the current timestep (data row index)
        """
        moer = self.data.iloc[timestep]['MOER']
        if not self.fridge.on:
            lbs_co2 = 0
        else:
            lbs_co2 = self._lbs_co2_from_moer(moer)
        self.total_lbs_co2 += lbs_co2
        hist_avg_moer = self.data.iloc[timestep]['hist_avg_moer_at_time']

        row_data = [self.current_time, round(self.fridge.current_temp, 2), self.fridge.on, moer, lbs_co2,
                    hist_avg_moer]
        str_row_data = [str(field) for field in row_data]
        self.outfile.write(",".join(str_row_data) + "\n")
        return

    def _lbs_co2_from_moer(self, moer):
        """
        Calculates the lbs of CO2 that would be generated if the refrigerator runs during a timestep with this MOER.

        :param moer: the MOER from which to calculate lbs CO2
        :return: the lbs CO2, rounded to 8 decimal places
        """
        megawatts_per_watt = 1 / 1000000
        hours_per_minute = 1 / 60
        return round(moer * (self.fridge.WATTAGE * megawatts_per_watt) * (self.mins_per_timestep * hours_per_minute), 8)

    def _print_co2_emissions(self):
        print("=" * 50)
        print("Total refrigerator run time: ", self.current_time, " mins")
        print("Total lbs CO2 emitted: ", self.total_lbs_co2)

    def _print_sim_run_time(self, start_time, sim_id):
        """
        Prints a formatted message indicating time elapsed since start_time for the simulation identified by sim_id.

        :param start_time: simulation start time, in seconds
        :param sim_id: a human-readable string identifying the simulation being timed
        """
        end_time = time.time()
        total_seconds = round(end_time - start_time, 2)
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        print("Simulation '{}' duration: {} min {} sec".format(sim_id, minutes, seconds))
