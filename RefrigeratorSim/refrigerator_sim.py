import argparse
import os
import pandas as pd
import subprocess
from simulator import Simulator


def parse_args():
    """ Parses command line arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('--best', action='store_true', default=False,
                        help='Run best simulation (incorporates zero-moers, forecast, and historicals)')
    parser.add_argument('--zeroes', action='store_true', default=False,
                        help='Run model incorporating simple decision on zero-MOER timesteps.')
    parser.add_argument('--forecast', action='store_true', default=False,
                        help='Run model using 1-hr forecast window.')
    parser.add_argument('--hist', action='store_true', default=False,
                        help='Run model using 1-hr forecast and historical avgs.')
    parser.add_argument('--all', action='store_true', default=False,
                        help='Run all four successively improving models '
                        '(no data, zeroes only, forecast, forecast and history)')
    parser.add_argument('--moer_avgs', action='store_true', default=False,
                        help='Produce plot of average MOER data.')
    parser.add_argument('--data_path', action='store', default='MOER_data/MOERS.csv', help='Path to dataset.')
    parser.add_argument('--timesteps', action='store', default='all',
                        help='The number of timesteps to run for this simulation, defaults to size of dataset.')
    parser.add_argument('--clean', default=False, action='store_true',
                        help='Delete the current output data directory before starting simulations.')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    output_dir = "./output_data/"

    # Clean output directory?
    if args.clean:
        subprocess.run(["rm", "-rf", output_dir])

    # Create output dir for file collection
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # Read initial MOER data and cut off first day (pre 3-1-19)
    all_moer_data = pd.read_csv(args.data_path)
    initial_historical_data = all_moer_data[:288]
    sim_moer_data = all_moer_data[288:-1].reset_index(drop=True)

    # Number of timesteps (data rows) defaults to full dataset (shrink via command line args for shorter testing cycles)
    if args.timesteps == 'all':
        args.timesteps = sim_moer_data.shape[0]
    else:
        args.timesteps = int(args.timesteps)

    simulator = Simulator(sim_moer_data, output_dir, args.timesteps)

    # Run simulations based on arguments supplied at command line.

    # *Only* create a plot of average moer values at each timestep.
    if args.moer_avgs:
        simulator.plot_avg_moers()
        exit(0)

    # Run all simulations in order of increasing performance
    if args.all:  # run all simulation options
        simulator.run()
        simulator.run(use_zeroes=True)
        simulator.run(use_zeroes=True, use_forecast=True)
        simulator.run(use_zeroes=True, use_forecast=True, use_hist=True)
        exit(0)

    if args.best:
        simulator.run(use_zeroes=True, use_forecast=True, use_hist=True)
        exit(0)

    # Otherwise, run the simulation as specified on command line.
    simulator.run(use_zeroes=args.zeroes, use_forecast=args.forecast, use_hist=args.hist)
