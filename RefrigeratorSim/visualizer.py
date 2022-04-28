import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd


class Visualizer:
    """ A class for visualizing the output data of an AER simulation. """

    def __init__(self, simulator):
        """
        :param simulator: A reference to the Simulator object this Visualizer belongs to.
        """
        self.simulator = simulator

    def plot(self, path_to_data):
        """ Generate and save a pdf plot displaying simulation results including:
                - The internal temperature of the refrigerator, as a function of time
                - The MOER data at each timestep of the simulation
                - The cumulative total lbs of CO2 that the refrigerator has consumed as a function of time

        Note: plot will be saved in output directory specified in Simulator object.

        :param path_to_data: the path to the csv file containing simulation data.
        """
        data = pd.read_csv(path_to_data)
        sim_id = path_to_data.lstrip(self.simulator.output_dir).rstrip('.csv').lstrip('/sim_output_')

        fig, axs = plt.subplots(3, 1, sharex=True, gridspec_kw={'hspace': 0})
        fig.set_size_inches(12, 7)
        title_suffix = " ".join([string.capitalize() for string in sim_id.split("_")])
        fig.suptitle("Simple AER Simulation: " + title_suffix)

        # plot fridge temp color-coded by on/off
        for t1, t2, status, y1, y2 in zip(data['time'],
                                          data['time'][1:],
                                          data['fridge_on'],
                                          data['fridge_temp'],
                                          data['fridge_temp'][1:]):
            if status:
                axs[0].plot([t1, t2], [y1, y2], 'b')
            else:
                axs[0].plot([t1, t2], [y1, y2], 'r')
        axs[0].set_ylabel('Refrigerator \nTemperature \n(F)', rotation=0, labelpad=42)
        axs[0].set_ylim([30, 45])
        axs[0].set_yticks(range(33, 44))

        legend_elements = [Line2D([0], [0], color='b', lw=4, label='On'),
                           Line2D([0], [0], color='r', lw=4, label='Off')]
        axs[0].legend(handles=legend_elements)

        # plot moer
        axs[1].set_ylabel('MOER \n(lbs CO2 / Mwh)', rotation=0, labelpad=42)
        axs[1].plot(data["time"], data["moer"])

        # plot cumulative CO2 usage
        cumulative_total = 0
        for t1, co2, t2 in zip(data['time'], data['lbs_co2'], data['time'][1:]):
            new_total = cumulative_total + co2
            axs[2].plot([t1, t2], [cumulative_total, new_total], 'b')
            cumulative_total = new_total
        cumulative_total += data['lbs_co2'][data.shape[0] - 1] # don't forget last entry that's getting lost by the zip
        axs[2].set_ylabel('Cumulative \nlbs CO2', rotation=0, labelpad=42)

        axs[2].set_xlabel('Elapsed Time (min)')
        xticks = data['time'][::288 // 2]
        mapper = map(self._create_xlabel_for_time, xticks)
        xtick_labels = list(mapper)
        axs[2].set_xticks(xticks)
        axs[2].set_xticklabels(xtick_labels, rotation=50, fontsize=8)

        fig.tight_layout()

        axs[2].text(0.95, 0.01, 'Total lbs CO2 emitted: ' + str(round(cumulative_total, 4)),
                    verticalalignment='bottom', horizontalalignment='right',
                    transform=axs[2].transAxes,
                    color='green', fontsize=15)

        fig.savefig(self.simulator.output_dir.rstrip('/') + '/' + 'plots_' + sim_id + ".pdf")
        return

    def plot_avg_moers(self, path_to_data):
        """ Generate and save a plot of the average MOER for each time of day, for duration of simulation timespan.

        Note: plot will be saved in output directory specified in Simulator object.

        :param path_to_data: the path to the csv file containing simulation data.
        """
        data = pd.read_csv(path_to_data)
        fig, ax = plt.subplots()
        ax.set_ylabel('AVG MOER \n(lbs CO2 / Mwh)', rotation=0, labelpad=42)
        ax.plot(data["time"], data["avg_moer_at_time"])
        fig.set_size_inches(8, 5)
        fig.suptitle("Average Historical MOER: Granularity = timestep")
        fig.tight_layout()
        fig.savefig(self.simulator.output_dir.rstrip('/') + '/' + 'avgMOERs_timestep_granularity.pdf')
        return

    def _create_xlabel_for_time(self, minutes_elapsed):
        minutes_per_day = 60 * 24
        day = minutes_elapsed // minutes_per_day
        hour = (minutes_elapsed % minutes_per_day) // 60
        minutes = (minutes_elapsed % minutes_per_day) % 60
        return "3-{} {}:{:0>2d}".format(day, hour, minutes)
